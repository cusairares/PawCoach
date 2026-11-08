// Camera preview placeholder: draws a dog silhouette in the detected pose.
// Will be replaced by the real video stream (BACKEND_QUESTIONS.md, Q5).

const BOX = {
  sitting: { left: "27%", top: "18%", width: "46%", height: "70%" },
  standing: { left: "16%", top: "28%", width: "68%", height: "58%" },
  lying: { left: "12%", top: "52%", width: "76%", height: "36%" },
};

function Silhouette({ pose }) {
  if (pose === "standing") {
    return (
      <svg viewBox="0 0 400 300" className="cam-dog" style={{ left: "16%", top: "26%", width: "68%" }} aria-hidden="true">
        <ellipse cx="215" cy="140" rx="115" ry="52" />
        <circle cx="95" cy="95" r="48" className="head" />
        <rect x="120" y="160" width="26" height="100" rx="13" /><rect x="160" y="160" width="26" height="100" rx="13" />
        <rect x="250" y="160" width="26" height="100" rx="13" /><rect x="290" y="160" width="26" height="100" rx="13" />
      </svg>
    );
  }
  if (pose === "lying") {
    return (
      <svg viewBox="0 0 400 200" className="cam-dog" style={{ left: "12%", top: "52%", width: "76%" }} aria-hidden="true">
        <ellipse cx="215" cy="120" rx="140" ry="52" />
        <circle cx="95" cy="80" r="50" className="head" />
        <ellipse cx="70" cy="52" rx="16" ry="34" transform="rotate(-25 70 52)" />
        <rect x="40" y="145" width="120" height="22" rx="11" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 400 300" className="cam-dog" style={{ left: "30%", top: "20%", width: "40%" }} aria-hidden="true">
      <ellipse cx="200" cy="215" rx="85" ry="70" />
      <circle cx="200" cy="105" r="62" className="head" />
      <ellipse cx="200" cy="140" rx="34" ry="24" className="muzzle" />
      <ellipse cx="145" cy="80" rx="20" ry="44" transform="rotate(-18 145 80)" />
      <ellipse cx="255" cy="80" rx="20" ry="44" transform="rotate(18 255 80)" />
    </svg>
  );
}

export default function CameraView({ pose, poseLabel, confidence, children }) {
  return (
    <div className="cam" role="img" aria-label={`Live camera: dog is ${poseLabel?.toLowerCase() ?? "not in view"}`}>
      <div className="cam-floor" />
      {pose && BOX[pose] && (
        <>
          <Silhouette pose={pose} />
          <div className="cam-box" style={BOX[pose]} />
        </>
      )}
      <span className="cam-chip cam-chip--live"><span className="rec-dot" />LIVE</span>
      {pose && <span className="cam-chip cam-chip--pose">{poseLabel} · {Math.round(confidence * 100)}%</span>}
      {children}
    </div>
  );
}
