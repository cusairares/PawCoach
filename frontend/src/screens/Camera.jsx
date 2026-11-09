import { BackLink, StatusPill } from "../components/ui.jsx";
import { useStore } from "../store.jsx";

const OPTIONS = [
  ["nightVision", "Automatic night vision"],
  ["microphone", "Microphone for “Quiet”"],
  ["speaker", "Speaker for your voice"],
];

export default function Camera() {
  const { camera, setCamera, showToast, source } = useStore();

  return (
    <div className="screen">
      <BackLink to="/settings" label="Settings" />
      <header className="row-between">
        <h1>Camera</h1>
        <StatusPill online={camera.online} />
      </header>

      <section className="card stack-12" aria-labelledby="zone-h">
        <div className="stack-0">
          <h2 id="zone-h">Living room</h2>
          <span className="muted small">
            {source === "api" && !camera.online ? "No camera connected · the server simulates a dog" : "4MP · night vision"}
          </span>
        </div>
        <div className="zone-preview" role="img" aria-label="Camera preview with the training zone marked">
          <div className="cam-floor" />
          <div className="zone-box"><span>Training zone</span></div>
        </div>
        <span className="muted-2 small">Your dog is only tracked inside the marked zone. Keep the feeder in frame.</span>
        <button type="button" className="btn btn--soft" onClick={() => showToast("Zone editing isn't in the mockup yet")}>
          Redraw zone
        </button>
      </section>

      <section className="card card--list" aria-label="Camera options">
        {OPTIONS.map(([key, label]) => (
          <label key={key} className="check-row">
            {label}
            <input type="checkbox" checked={camera[key]}
              onChange={(e) => setCamera((c) => ({ ...c, [key]: e.target.checked }))} />
          </label>
        ))}
      </section>

      <button type="button" className="btn btn--dashed" onClick={() => showToast("Pairing isn't in the mockup yet")}>
        + Add a camera
      </button>
    </div>
  );
}
