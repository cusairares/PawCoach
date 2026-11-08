"""Run complete two-stage inference (Detector + Posture + Consensus) on a sample video.
Saves annotated output video to verify real-world performance.
"""
import cv2
import time
from pathlib import Path
from src.detector import DogDetector, square_crop
from src.posture import PostureClassifier
from src.consensus import ConsensusBuffer, StateTracker
from src.config import POSTURE_LABELS, EngineConfig

def run_video_pipeline(video_path: str, output_path: str):
    print(f"\n[Pipeline] Initializing models for {video_path}...")
    detector = DogDetector(score_threshold=0.45)
    classifier = PostureClassifier()
    config = EngineConfig()
    
    buffer = ConsensusBuffer(labels=POSTURE_LABELS, window_s=1.0, min_fill=0.5, min_entries=5)
    tracker = StateTracker(enter_threshold=0.55, exit_threshold=0.35)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Resize output if vertical/huge for faster writing
    out_w, out_h = (540, 960) if h > w else (640, 480)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (out_w, out_h))

    prev_box = None
    frame_idx = 0
    t_sim = 0.0

    print("[Pipeline] Processing frames...")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        t_sim += 1.0 / fps
        frame_idx += 1

        # Stage 1: Dog detection
        det = detector.detect(frame, previous=prev_box)
        probs = None
        crop = None

        if det is not None:
            prev_box = det.box
            crop = square_crop(frame, det.box, padding=config.box_padding)
            # Stage 2: Posture classification
            probs = classifier.predict(crop)

        # Feed to consensus buffer
        buffer.push(t_sim, probs)
        vote = buffer.vote(t_sim)
        state_changed = tracker.update(vote, t_sim)

        # Draw Overlay
        disp = cv2.resize(frame, (out_w, out_h))
        scale_x = out_w / w
        scale_y = out_h / h

        if det is not None:
            x1, y1, x2, y2 = det.box
            cv2.rectangle(disp, (int(x1*scale_x), int(y1*scale_y)), (int(x2*scale_x), int(y2*scale_y)), (0, 255, 0), 2)
            if probs is not None:
                top_p_idx = probs.argmax()
                raw_txt = f"{POSTURE_LABELS[top_p_idx]}: {probs[top_p_idx]*100:.0f}%"
                cv2.putText(disp, raw_txt, (int(x1*scale_x), int(y1*scale_y) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Consensus HUD
        hud_bg = (30, 30, 30)
        cv2.rectangle(disp, (10, 10), (out_w - 10, 90), hud_bg, -1)
        confirmed_txt = f"CONFIRMED STATE: {str(tracker.state).upper()}"
        held_txt = f"Held: {tracker.held_for(t_sim):.1f}s | Vote: {vote.label or 'none'} ({vote.score*100:.0f}%)"
        
        state_color = (0, 255, 255) if tracker.state else (150, 150, 150)
        if tracker.state == "sitting":
            state_color = (0, 255, 0)

        cv2.putText(disp, confirmed_txt, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, state_color, 2)
        cv2.putText(disp, held_txt, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        writer.write(disp)

    cap.release()
    writer.release()
    print(f"[Pipeline] Finished processing {frame_idx} frames. Output saved to {output_path}")

if __name__ == "__main__":
    run_video_pipeline("samples/dog1.mp4", "samples/dog1_annotated.mp4")
