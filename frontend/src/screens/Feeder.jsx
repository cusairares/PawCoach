import Icon from "../components/Icon.jsx";
import { BackLink, Progress, Segmented, StatusPill } from "../components/ui.jsx";
import { useStore } from "../store.jsx";

export default function Feeder() {
  const { feeder, setFeeder, showToast, testTreat, source, health } = useStore();
  const hardware = source !== "api" ? "Open source · ESP32 · firmware 1.2.0"
    : health?.feeder === "SerialFeeder" ? "Open source · ESP32 on USB" : "Simulated feeder (no ESP32 connected)";
  const hopper = Math.round(feeder.hopper);

  return (
    <div className="screen">
      <BackLink to="/settings" label="Settings" />
      <header className="row-between">
        <h1>Feeder</h1>
        <StatusPill online={feeder.online} />
      </header>

      <section className="card stack-10" aria-label="Hopper">
        <div className="row-between baseline">
          <strong>Hopper</strong>
          <strong className="big-number">{hopper}%</strong>
        </div>
        <Progress value={hopper} tone="honey" thick />
        <span className="muted small">Lasts about {Math.max(1, Math.round(hopper / 22))} days at current schedules</span>
        <button type="button" className="btn btn--soft"
          onClick={() => { setFeeder((f) => ({ ...f, hopper: 100 })); showToast("Hopper marked as full"); }}>
          I refilled it
        </button>
      </section>

      <section className="card stack-12" aria-labelledby="portion-h">
        <h2 id="portion-h">Portion size</h2>
        <Segmented label="Portion size" value={feeder.portion}
          onChange={(portion) => setFeeder((f) => ({ ...f, portion }))}
          options={[["small", "Small"], ["medium", "Medium"], ["large", "Large"]]} />
        <button type="button" className="btn btn--peach"
          onClick={async () => showToast((await testTreat()) ? "Test treat dispensed" : "The feeder didn't respond")}>
          Dispense a test treat
        </button>
      </section>

      <button type="button" className="card nav-row" onClick={() => showToast("Technical details aren't in the mockup yet")}>
        <span className="stack-0 left">
          <strong>Technical details</strong>
          <span className="muted small">{hardware}</span>
        </span>
        <Icon name="chevronRight" size={18} className="muted" />
      </button>

      <button type="button" className="btn btn--dashed" onClick={() => showToast("Pairing isn't in the mockup yet")}>
        + Add a feeder
      </button>
    </div>
  );
}
