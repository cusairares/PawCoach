"""Main execution loop for Raspberry Pi Smart Feeder.
Wires DogDetector (ONNX) -> PostureClassifier (NumPy) -> ConsensusBuffer -> BehaviorController.
"""
import argparse
import time
import cv2

from src.detector import DogDetector
from src.posture import PostureClassifier
from src.consensus import ConsensusBuffer, StateTracker
from src.behavior import BehaviorController
from src.config import POSTURE_LABELS, EngineConfig, SettingsStore
from src.audio import AudioPlayer
from src.feeder import MockFeeder, SerialFeeder
from src.event_log import EventLog

def run_feeder(camera_index: int = 0, serial_port: str = None, target_fps: float = 15.0):
    print("=== Starting Smart Feeder Engine ===")
    config = EngineConfig()
    settings = SettingsStore()
    event_log = EventLog()
    audio = AudioPlayer()
    
    if serial_port:
        feeder = SerialFeeder(port=serial_port)
        print(f"[Feeder] Connected to hardware on {serial_port}")
    else:
        feeder = MockFeeder()
        print("[Feeder] Running with MockFeeder (logs treats without hardware)")

    detector = DogDetector(score_threshold=config.detector_score_threshold, imgsz=config.pose_imgsz)
    classifier = PostureClassifier()

    passive_tracker = StateTracker(enter_threshold=config.passive_threshold, exit_threshold=config.exit_threshold)
    active_tracker = StateTracker(enter_threshold=config.active_threshold, exit_threshold=config.exit_threshold)
    buffer = ConsensusBuffer(labels=POSTURE_LABELS, window_s=config.window_s, min_fill=config.min_fill, min_entries=config.min_entries)

    controller = BehaviorController(audio=audio, feeder=feeder, event_log=event_log,
                                    settings=settings, config=config)

    cap = cv2.VideoCapture(camera_index)
    frame_interval = 1.0 / target_fps
    prev_box = None

    print(f"[Feeder] Camera opened. Running loop @ {target_fps} FPS...")
    try:
        while True:
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]

            # Stage 1: Detect dog & 24 keypoints
            det = detector.detect(frame, previous=prev_box)
            probs = None

            if det is not None:
                prev_box = det.box
                # Stage 2: Biomechanical Posture Classification
                probs = classifier.predict_detection(det, frame_width=float(w),
                                                     min_visible_kpts=config.min_visible_keypoints,
                                                     min_confidence=config.posture_min_confidence)

            # Consensus & State Trackers
            now = time.time()
            buffer.push(now, probs)
            vote = buffer.vote(now)
            passive_tracker.update(vote, now)
            active_tracker.update(vote, now)

            # Behavior Controller (passive treat dispense or command obedience)
            events = controller.update(now, passive=passive_tracker, active=active_tracker)
            for ev in events:
                print(f"[EVENT] {ev.kind}: {ev.target or ev.detected} (treat dispensed: {ev.treat})")

            elapsed = time.time() - t0
            sleep_time = max(0.0, frame_interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[Feeder] Stopping engine...")
    finally:
        cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Feeder Raspberry Pi Engine")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--serial-port", type=str, default=None, help="Serial port to ESP32 / Arduino (e.g. /dev/ttyUSB0)")
    parser.add_argument("--fps", type=float, default=15.0, help="Target FPS")
    args = parser.parse_args()

    run_feeder(camera_index=args.camera, serial_port=args.serial_port, target_fps=args.fps)
