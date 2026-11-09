"""API tests (FastAPI TestClient). Needs: pip install -r requirements-server.txt

The engine thread is not started; tests step the runtime by hand with a fake clock.
"""
import random
import tempfile
import unittest
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from server.main import create_app  # noqa: E402
from src.app_runtime import AppRuntime  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.rt = AppRuntime(mode="mock", data_dir=Path(tempfile.mkdtemp()), clock=self.clock,
                             rng=random.Random(1), highlights=False, demo=True)
        self.api = TestClient(create_app(self.rt, run_loop=False))
        self.bruno = next(d for d in self.api.get("/api/dogs").json() if d["name"] == "Bruno")

    def tearDown(self) -> None:
        self.rt.stop()

    def run_for(self, seconds: float, dt: float = 0.1) -> None:
        for _ in range(int(seconds / dt)):
            self.clock.t += dt
            self.rt.step()

    def test_health_and_status(self) -> None:
        self.assertEqual(self.api.get("/api/health").json()["mode"], "mock")
        self.run_for(1.0)
        st = self.api.get("/api/status").json()
        self.assertEqual(st["dog"]["name"], "Bruno")
        self.assertIn("posture", st)
        self.assertIn("recent_events", st)

    def test_dogs_have_what_the_app_shows(self) -> None:
        dogs = self.api.get("/api/dogs").json()
        self.assertEqual([d["name"] for d in dogs], ["Bruno", "Luna", "Toby"])
        luna = dogs[1]
        self.assertEqual(luna["pronoun"], "she")
        for key in ("treats_today", "daily_treat_limit", "success_rate_7d", "streak_days", "avg_reaction_s",
                    "exercises", "week", "caught_today"):
            self.assertIn(key, luna)
        self.assertEqual(len(luna["week"]), 7)
        self.assertEqual(luna["streak_days"], 21)
        self.assertEqual(self.api.get("/api/dogs/999").status_code, 404)

    def test_command_success_through_the_api(self) -> None:
        self.run_for(0.5)
        r = self.api.post("/api/commands", json={"exercise": "sit"})
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(self.api.post("/api/commands", json={"exercise": "down"}).status_code, 409)
        self.run_for(7.0)
        kinds = [e["type"] for e in self.api.get("/api/status").json()["recent_events"]]
        self.assertIn("command_success", kinds)

    def test_bad_requests(self) -> None:
        self.assertEqual(self.api.post("/api/commands", json={"exercise": "fly"}).status_code, 400)
        self.assertEqual(self.api.post("/api/commands", json={"exercise": "paw"}).status_code, 400)
        self.assertEqual(self.api.post("/api/commands", json={}).status_code, 422)
        self.assertEqual(self.api.patch("/api/settings", json={"nope": 1}).status_code, 422)

    def test_treat_and_feeder_test(self) -> None:
        before = self.api.get(f"/api/dogs/{self.bruno['id']}").json()["treats_today"]
        r = self.api.post("/api/treat").json()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["treats_today"], before + 1)
        self.assertTrue(self.api.post("/api/feeder/test").json()["ok"])
        self.assertEqual(self.api.get(f"/api/dogs/{self.bruno['id']}").json()["treats_today"], before + 1)

    def test_select_dog_and_stage(self) -> None:
        toby = next(d for d in self.api.get("/api/dogs").json() if d["name"] == "Toby")
        self.assertEqual(self.api.post(f"/api/dogs/{toby['id']}/select").status_code, 200)
        self.run_for(0.3)
        self.assertEqual(self.api.get("/api/status").json()["dog"]["name"], "Toby")
        r = self.api.patch(f"/api/dogs/{toby['id']}/exercises/sit", json={"stage": "train"})
        self.assertEqual(r.json()["stage"], "train")
        self.assertEqual(self.api.patch(f"/api/dogs/{toby['id']}/exercises/sit", json={"stage": "x"}).status_code,
                         422)

    def test_schedules_crud(self) -> None:
        schedules = self.api.get("/api/schedules").json()
        self.assertEqual(len(schedules), 5)
        sid = schedules[0]["id"]
        r = self.api.patch(f"/api/schedules/{sid}", json={"enabled": False, "max_treats": 6}).json()
        self.assertEqual((r["enabled"], r["max_treats"]), (False, 6))
        new = self.api.post("/api/schedules", json={"dog_id": self.bruno["id"], "kind": "train",
                                                    "exercise_ids": ["sit"], "times": ["07:30"]})
        self.assertEqual(new.status_code, 201, new.text)
        bad = self.api.post("/api/schedules", json={"dog_id": self.bruno["id"], "kind": "learn",
                                                    "exercise_ids": ["sit"]})
        self.assertEqual(bad.status_code, 400)                  # learn needs start and end
        self.assertTrue(self.api.delete(f"/api/schedules/{new.json()['id']}").json()["ok"])
        self.assertEqual(len(self.api.get("/api/schedules").json()), 5)

    def test_add_and_archive_dog(self) -> None:
        r = self.api.post("/api/dogs", json={"name": "Rex", "breed": "Mixed", "pronoun": "he",
                                             "age_text": "2 yrs", "image_url": "/dogs/preset_1.jpg"})
        self.assertEqual(r.status_code, 201, r.text)
        rex = r.json()
        self.assertEqual(rex["age_text"], "2 yrs")
        self.assertEqual(rex["image_url"], "/dogs/preset_1.jpg")
        self.assertEqual(len(rex["exercises"]), 5)
        self.assertEqual(self.api.patch(f"/api/dogs/{rex['id']}", json={"weight_kg": 12}).json()["weight_kg"], 12)
        self.assertTrue(self.api.delete(f"/api/dogs/{rex['id']}").json()["ok"])
        self.assertEqual(self.api.get(f"/api/dogs/{rex['id']}").status_code, 404)

    def test_moments_and_leaderboard_endpoints(self) -> None:
        moments = self.api.get("/api/moments/random?limit=3&clientId=u1").json()
        self.assertEqual(len(moments), 3)
        mid = moments[0]["id"]
        orig_likes = moments[0]["likesCount"]
        like_res = self.api.post(f"/api/moments/{mid}/like", json={"clientId": "u1", "liked": True}).json()
        self.assertTrue(like_res["liked"])
        self.assertEqual(like_res["likesCount"], orig_likes + 1)

        lb = self.api.get("/api/leaderboard?category=score&scope=city").json()
        self.assertEqual(len(lb), 10)
        self.assertEqual(lb[0]["rank"], 1)
        # the leaderboard lives in its own file inside the server's data folder, next to app.db
        self.assertTrue((self.rt.data_dir / "app" / "community.db").exists())

    def test_snapshot_and_stats(self) -> None:
        self.run_for(0.5)
        r = self.api.get("/api/snapshot.jpg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "image/jpeg")
        self.assertEqual(len(self.api.get("/api/stats/daily?days=7").json()), 7)
        self.assertEqual(self.api.post("/api/sim/pose", json={"pose": "lying"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
