import tempfile
import unittest
from pathlib import Path
from src.app_store import AppStore, Dog

class MomentsAndIndexingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AppStore(Path(self.tmp.name) / "app.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_database_indexes_exist(self):
        with self.store._lock:
            indexes = {r[0] for r in self.store._conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
        self.assertIn("idx_moments_active_id", indexes)
        self.assertIn("idx_moments_dog_id", indexes)
        self.assertIn("idx_moment_likes_moment", indexes)

    def test_dog_creation_with_image_and_age(self):
        dog = self.store.add_dog(Dog("Rocky", breed="Malinois", age_text="3 yrs", weight_kg=28.5, image_url="/dogs/rocky.jpg"))
        fetched = self.store.dog(dog.id)
        self.assertEqual(fetched.name, "Rocky")
        self.assertEqual(fetched.age_text, "3 yrs")
        self.assertEqual(fetched.weight_kg, 28.5)
        self.assertEqual(fetched.image_url, "/dogs/rocky.jpg")

    def test_random_moments_selection_and_exclusion(self):
        # Initial seed moments are present
        moments = self.store.random_moments(limit=3, client_id="user_1")
        self.assertEqual(len(moments), 3)
        first_id = moments[0]["id"]
        # Exclude first_id
        filtered = self.store.random_moments(limit=3, exclude_ids=[first_id], client_id="user_1")
        self.assertNotIn(first_id, [m["id"] for m in filtered])

    def test_idempotent_likes_and_ap_consistency(self):
        moments = self.store.random_moments(limit=1, client_id="user_42")
        mid = moments[0]["id"]
        orig_count = moments[0]["likes_count"]

        # Like once
        res1 = self.store.set_moment_like(mid, "user_42", True)
        self.assertTrue(res1["liked"])
        self.assertEqual(res1["likes_count"], orig_count + 1)

        # Like again (idempotent duplicate request)
        res2 = self.store.set_moment_like(mid, "user_42", True)
        self.assertTrue(res2["liked"])
        self.assertEqual(res2["likes_count"], orig_count + 1)

        # Check random_moments returns liked=True
        refetched = [m for m in self.store.random_moments(limit=10, client_id="user_42") if m["id"] == mid][0]
        self.assertTrue(refetched["liked"])

        # Unlike
        res3 = self.store.set_moment_like(mid, "user_42", False)
        self.assertFalse(res3["liked"])
        self.assertEqual(res3["likes_count"], orig_count)
