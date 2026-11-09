// Camera preview: shows real dog photo matching detected pose and detection zone.
const POSE_IMAGES = {
  sitting: "/dogs/pose_sitting.jpg",
  standing: "/dogs/pose_standing.jpg",
  lying: "/dogs/pose_lying.jpg",
};

const BOX = {
  sitting: { left: "24%", top: "16%", width: "52%", height: "72%" },
  standing: { left: "16%", top: "24%", width: "68%", height: "62%" },
  lying: { left: "12%", top: "45%", width: "76%", height: "45%" },
};

export default function CameraView({ pose, poseLabel, confidence, children }) {
  const imgSrc = (pose && POSE_IMAGES[pose]) || "/dogs/living_room_dog.jpg";

  return (
    <div className="cam" role="img" aria-label={`Live camera: dog is ${poseLabel?.toLowerCase() ?? "not in view"}`}>
      <img
        src={imgSrc}
        alt={pose ? `Dog ${pose}` : "Camera view"}
        className="cam-img-feed"
        onError={(e) => { e.currentTarget.src = "/dogs/living_room_dog.jpg"; }}
      />
      <div className="cam-overlay-shade" />

      {pose && BOX[pose] && (
        <div className="cam-box" style={BOX[pose]}>
          <span className="cam-box-label">{poseLabel}</span>
        </div>
      )}

      <span className="cam-chip cam-chip--live"><span className="rec-dot" />LIVE</span>
      {pose && <span className="cam-chip cam-chip--pose">{poseLabel} · {Math.round(confidence * 100)}%</span>}
      {children}
    </div>
  );
}
