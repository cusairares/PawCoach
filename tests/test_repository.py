import tempfile
import unittest
from pathlib import Path

from src import repository
from src.app_store import AppStore, Dog
from src.repository import IPetRepository, SQLiteRepository, get_repository


class PetRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_repo.db"
        self.repo = SQLiteRepository(self.db_path)

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_implements_interface(self):
        self.assertIsInstance(self.repo, IPetRepository)

    def test_initial_seed_dogs_loaded(self):
        dogs = self.repo.get_dogs()
        self.assertEqual(len(dogs), 3)
        names = [d["name"] for d in dogs]
        self.assertIn("Bruno", names)
        self.assertIn("Luna", names)
        self.assertIn("Toby", names)

        bruno = self.repo.get_dog("bruno")
        self.assertIsNotNone(bruno)
        self.assertEqual(bruno["breed"], "Labrador")
        self.assertEqual(bruno["treatLimit"], 35)
        self.assertEqual(len(bruno["week"]), 7)
        self.assertTrue(len(bruno["exercises"]) >= 3)

    def test_create_and_update_dog(self):
        new_dog = self.repo.create_dog({
            "name": "Rex",
            "breed": "German Shepherd",
            "age": "4 yrs",
            "weight": "34 kg",
            "image": "/dogs/default.jpg",
        })
        self.assertEqual(new_dog["name"], "Rex")
        self.assertEqual(len(self.repo.get_dogs()), 4)

        updated = self.repo.update_dog(new_dog["id"], {"weight": "35 kg"})
        self.assertEqual(updated["weight"], "35 kg")

    def test_give_treat_and_hopper_update(self):
        bruno = self.repo.get_dog("bruno")
        initial_treats = bruno["treatsToday"]
        initial_hopper = self.repo.get_devices()["feeder"]["hopper"]

        res = self.repo.give_treat("bruno")
        self.assertTrue(res["ok"])
        self.assertEqual(res["treatsToday"], initial_treats + 1)
        self.assertEqual(res["hopper"], round(initial_hopper - 0.5, 1))

    def test_exercise_stage_update(self):
        updated = self.repo.set_exercise_stage("bruno", "down", "train")
        down_ex = next(e for e in updated["exercises"] if e["id"] == "down")
        self.assertEqual(down_ex["stage"], "train")

    def test_schedules_crud(self):
        schedules = self.repo.get_schedules()
        self.assertEqual(len(schedules), 5)

        first_id = schedules[0]["id"]
        updated = self.repo.update_schedule(first_id, {"on": False, "max": 15})
        self.assertFalse(updated["on"])
        self.assertEqual(updated["max"], 15)

    def test_random_moments_and_idempotent_likes(self):
        moments = self.repo.get_random_moments(limit=2, client_id="client_a")
        self.assertEqual(len(moments), 2)
        mid = moments[0]["id"]
        initial_likes = moments[0]["likesCount"]

        # Like
        res1 = self.repo.set_moment_like(mid, "client_a", True)
        self.assertTrue(res1["liked"])
        self.assertEqual(res1["likesCount"], initial_likes + 1)

        # Idempotent like retry
        res2 = self.repo.set_moment_like(mid, "client_a", True)
        self.assertTrue(res2["liked"])
        self.assertEqual(res2["likesCount"], initial_likes + 1)

        # Unlike
        res3 = self.repo.set_moment_like(mid, "client_a", False)
        self.assertFalse(res3["liked"])
        self.assertEqual(res3["likesCount"], initial_likes)

    def test_leaderboard_retrieval(self):
        entries = self.repo.get_leaderboard("score", "city")
        self.assertEqual(len(entries), 10)
        self.assertEqual(entries[0]["rank"], 1)
        self.assertEqual(entries[0]["name"], "Rocky")
        self.assertTrue(any(e["mine"] for e in entries))

    def test_device_settings(self):
        devices = self.repo.get_devices()
        self.assertIn("feeder", devices)
        self.assertIn("camera", devices)
        self.assertTrue(devices["camera"]["nightVision"])

        updated = self.repo.update_device("camera", {"nightVision": False})
        self.assertFalse(updated["nightVision"])


class SeparateDatabaseTest(unittest.TestCase):
    """The repository must never share a file with AppStore (their tables differ)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repository._DEFAULT_REPO = None

    def tearDown(self):
        if repository._DEFAULT_REPO is not None:
            repository._DEFAULT_REPO.close()
        repository._DEFAULT_REPO = None
        self.tmp.cleanup()

    def test_repository_and_app_store_live_side_by_side(self):
        app_dir = Path(self.tmp.name) / "app"
        repo = get_repository(app_dir / "community.db")
        self.assertEqual(len(repo.get_dogs()), 3)
        store = AppStore(app_dir / "app.db")
        store.add_dog(Dog("Rex"))
        self.assertEqual([d.name for d in store.dogs()], ["Rex"])
        self.assertIs(get_repository(), repo)                  # singleton
        store.close()


if __name__ == "__main__":
    unittest.main()
