"""Mock mode with the real classifier: the simulated dog's poses are demo-video frames that go
through DogDetector + PostureClassifier, so a cue only succeeds if the models confirm it."""
import importlib.util
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.app_runtime import AppRuntime
from src.app_store import Dog
from src.demo_footage import DEMO_SEGMENTS, DEMO_VIDEO, load_segments

HAVE_MODELS = (importlib.util.find_spec("cv2") is not None
               and importlib.util.find_spec("onnxruntime") is not None
               and DEMO_VIDEO.exists() and DEMO_SEGMENTS.exists())


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def run(rt, clock, seconds):
    out = []
    for _ in range(int(seconds * 10)):
        clock.t += 0.1
        out += rt.step(clock.t)
    return out


def results(events):
    return [e for e in events if e["type"] in ("command_success", "command_fail")]


class SegmentsTest(unittest.TestCase):
    def test_hard_segments_are_skipped_unless_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "segments.json"
            path.write_text(json.dumps({"segments": {
                "lying": [[1, 2], {"span": [5, 6], "hard": True}],
                "sitting": [{"span": [7, 8], "hard": True}],
                "standing": [[3, 2]],                                   # empty span: ignored
            }}))
            self.assertEqual(load_segments(path, include_hard=False), {"lying": [(1.0, 2.0)]})
            self.assertEqual(load_segments(path, include_hard=True),
                             {"lying": [(1.0, 2.0), (5.0, 6.0)], "sitting": [(7.0, 8.0)]})

    def test_repo_segments_cover_every_pose(self):
        segs = load_segments(DEMO_SEGMENTS, include_hard=False)
        self.assertEqual(set(segs), {"lying", "sitting", "standing"})


class FallbackTest(unittest.TestCase):
    def test_falls_back_to_synthetic_when_footage_cant_load(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("src.demo_footage.DemoFootage.__init__", side_effect=FileNotFoundError("video")):
            rt = AppRuntime(mode="mock", data_dir=tmp, highlights=False, sim_source="classifier")
            try:
                self.assertEqual(rt.sim_source, "synthetic")
                self.assertIn("classifier unavailable", rt.sim_note)
                rt.step(1.0)
                self.assertEqual(rt.status()["sim"]["source"], "synthetic")
            finally:
                rt.stop()

    def test_synthetic_stays_the_constructor_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            rt = AppRuntime(mode="mock", data_dir=tmp, highlights=False)
            try:
                self.assertIsNone(rt.footage)
                self.assertEqual(rt.sim_source, "synthetic")
            finally:
                rt.stop()


@unittest.skipUnless(HAVE_MODELS, "needs opencv, onnxruntime and the demo video")
class ClassifierMockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.rt = AppRuntime(mode="mock", data_dir=self.tmp.name, clock=self.clock, highlights=False,
                             rng=random.Random(5), sim_source="classifier")
        self.assertEqual(self.rt.sim_source, "classifier", self.rt.sim_note)
        dog = self.rt.store.add_dog(Dog("Bruno", daily_treat_limit=50))
        self.rt.select_dog(dog.id)
        self.rt.settings.update({"min_seconds_between_treats": 0})

    def tearDown(self):
        self.rt.stop()
        self.tmp.cleanup()

    def test_pose_comes_from_the_classifier(self):
        self.rt.set_sim_pose("standing")
        run(self.rt, self.clock, 2.0)
        st = self.rt.status()
        self.assertEqual(st["sim"]["source"], "classifier")
        self.assertIsNotNone(st["sim"]["clip_t"])
        self.assertIsNotNone(st["box"])                                # a real detector box
        self.assertEqual(st["frame_posture"]["label"], "standing")
        self.assertEqual(st["posture"]["state"], "standing")
        self.assertNotAlmostEqual(st["frame_posture"]["confidence"], 0.88 / 0.97, places=2)  # not synthetic

    def test_cue_succeeds_when_the_classifier_confirms_the_pose(self):
        self.rt.footage.segments = {"standing": [(13.6, 15.1)], "lying": [(12.0, 13.0)]}
        self.rt.set_sim_pose("standing")
        run(self.rt, self.clock, 2.0)
        self.rt.set_sim_pose("auto")
        self.rt.submit_command("down")
        out = results(run(self.rt, self.clock, 9))
        self.assertEqual([e["type"] for e in out], ["command_success"])
        self.assertGreater(out[0]["reaction_s"], 1.0)                  # obey delay + consensus window

    def test_cue_fails_when_the_classifier_misreads_the_pose(self):
        # clip 3: a dog lying on a bench that the current classifier reads as standing
        self.rt.footage.segments = {"standing": [(13.6, 15.1)], "lying": [(25.7, 27.4)]}
        self.rt.set_sim_pose("standing")
        run(self.rt, self.clock, 2.0)
        self.rt.set_sim_pose("auto")
        self.rt.submit_command("down")
        out = results(run(self.rt, self.clock, 9))
        self.assertEqual([(e["type"], e["detail"]) for e in out], [("command_fail", "timeout")])


if __name__ == "__main__":
    unittest.main()
