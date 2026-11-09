"""Runs the real models over the demo video, for the app's offline Live simulation.

    python tools/demo_timeline.py            (from the repo root)

1. DogDetector + PostureClassifier on every 2nd frame of ``video demo/video demo.mp4``
   -> ``frontend/public/demo/timeline.json``: the classifier's probabilities over time plus the
   hand-labelled segments from ``video demo/segments.json``. When the app can't reach the
   server, Live plays the demo video and decides cues from these numbers (same consensus
   window + thresholds as the backend), instead of just waiting and calling it a success.
2. Prints how often the classifier agrees with each labelled segment - use it to decide which
   segments to mark ``"hard": true`` after retraining the models.

Re-run it whenever the models, the video or segments.json change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from src.config import EngineConfig, POSTURE_LABELS  # noqa: E402
from src.demo_footage import DEMO_SEGMENTS, DEMO_VIDEO, crop_portrait, load_segments  # noqa: E402
from src.detector import DogDetector  # noqa: E402
from src.posture import PostureClassifier  # noqa: E402

OUT = ROOT / "frontend" / "public" / "demo" / "timeline.json"
STEP = 2                                     # every 2nd frame: 15 values per second of a 30 fps video


def main() -> None:
    cfg = EngineConfig()
    det = DogDetector(score_threshold=0.25, imgsz=cfg.pose_imgsz)      # same settings as the runtime
    clf = PostureClassifier()                                         # uses for recorded video
    cap = cv2.VideoCapture(str(DEMO_VIDEO))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    probs, prev, i = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % STEP == 0:
            frame = crop_portrait(frame)
            d = det.detect(frame, previous=prev)
            if d is None:
                probs.append(None)
            else:
                prev = d.box
                p = clf.predict_detection(d, frame_width=float(frame.shape[1]),
                                          min_visible_kpts=4, min_confidence=0.35)
                probs.append([round(float(v), 3) for v in p])
        i += 1
    cap.release()
    rate = fps / STEP

    all_segments = load_segments(DEMO_SEGMENTS, include_hard=True)
    easy = load_segments(DEMO_SEGMENTS, include_hard=False)
    print(f"{i} frames, {len(probs)} classified ({rate:g}/s)\n")
    print("segment            top-1   mean p(pose)   used by the mock dog")
    for pose, spans in all_segments.items():
        k = POSTURE_LABELS.index(pose)
        for s, e in spans:
            window = probs[int(s * rate):int(e * rate)]
            hits = sum(1 for p in window if p and int(np.argmax(p)) == k)
            mean = np.mean([p[k] if p else 0.0 for p in window]) if window else 0.0
            used = "yes" if (s, e) in easy.get(pose, []) else "no (hard)"
            print(f"{pose:8s} {s:5.1f}-{e:5.1f}   {hits / max(1, len(window)):4.0%}   {mean:10.2f}     {used}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "tools/demo_timeline.py - DogDetector + PostureClassifier on 'video demo/video demo.mp4'",
        "fps": rate,
        "labels": POSTURE_LABELS,
        "probs": probs,                                   # null = no dog detected
        "segments": {pose: [list(span) for span in spans] for pose, spans in easy.items()},
        "consensus": {"window_s": cfg.window_s, "min_fill": cfg.min_fill, "min_entries": cfg.min_entries,
                      "enter": cfg.active_threshold, "exit": cfg.exit_threshold},
    }, separators=(",", ":")), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
