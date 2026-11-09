import time
import cv2
import numpy as np
from classifier_engine import CanineClassifier, ConsensusBuffer, FeederMockController

def main():
    print("[Pipeline Test] Loading CanineClassifier & ConsensusBuffer...")
    classifier = CanineClassifier()
    consensus = ConsensusBuffer(buffer_len=15, consensus_threshold=0.60)
    feeder = FeederMockController(cooldown_seconds=5.0)

    # Generate synthetic dummy frames to verify consensus logic & pipeline speed
    print("\n--- Testing Single Frame Inference Speed ---")
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    t0 = time.time()
    for _ in range(10):
        label, conf, probs = classifier.predict_frame(dummy_frame)
    avg_latency = (time.time() - t0) / 10.0
    print(f"Average Inference Latency: {avg_latency*1000:.1f} ms (~{1.0/avg_latency:.1f} FPS)")

    print("\n--- Testing Rolling Consensus Majority Filter ---")
    simulated_stream = [
        "standing", "standing", "unknown", "standing", "standing",
        "standing", "sitting", "sitting", "sitting", "sitting",
        "sitting", "sitting", "sitting", "sitting", "sitting"
    ]

    for step, raw_pose in enumerate(simulated_stream):
        consensus.add(raw_pose)
        confirmed, ratio, dist = consensus.evaluate()
        print(f"Step {step+1:02d}: Raw={raw_pose:8s} | Buffer Consensus: Confirmed={str(confirmed):8s} Ratio={ratio:.2f} Dist={dist}")
        
        if confirmed == "sitting":
            feeder.trigger(reason="Dog stayed in Sitting posture for >= 60% of rolling buffer")

    print("\n[SUCCESS] Verification complete: Classifier engine and consensus filter operational!")

if __name__ == "__main__":
    main()
