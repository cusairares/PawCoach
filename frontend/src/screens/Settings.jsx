import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { Link } from "../router.jsx";
import { useStore } from "../store.jsx";

export default function Settings() {
  const { dogs, feeder, camera, schedules, showToast, source, health } = useStore();
  const connection = source === "api"
    ? `connected to the feeder${health?.mode === "mock" ? " (simulated dog)" : ""}`
    : "offline demo · start the server to connect";
  const activeSchedules = schedules.filter((s) => s.on).length;

  const rows = [
    { label: "Schedules", sub: `When they learn and when they train · ${activeSchedules} active`, icon: "calendar", tint: "honey", to: "/settings/schedules" },
    { label: "Feeder", sub: `${feeder.online ? "Online" : "Offline"} · hopper ${Math.round(feeder.hopper)}%`, icon: "feeder", tint: "sage", to: "/settings/feeder" },
    { label: "Camera", sub: `Living room · ${camera.online ? "online" : "offline"}`, icon: "camera", tint: "sky", to: "/settings/camera" },
    { label: "Your voice", sub: "Record cues in your own voice", icon: "mic", tint: "peach" },
    { label: "Notifications", sub: "Empty hopper, records, new moments", icon: "bell", tint: "honey" },
    { label: "Sharing moments", sub: "Who can see your dogs in Moments", icon: "share", tint: "sage" },
    { label: "Privacy", sub: "Live video never leaves your home", icon: "lock", tint: "sky" },
    { label: "Help & training guide", sub: "Step-by-step tips", icon: "help", tint: "peach" },
  ];

  return (
    <div className="screen">
      <h1>Settings</h1>

      <button type="button" className="card account-row" onClick={() => showToast("Account settings aren't in the mockup yet")}>
        <Avatar dog={{ name: "Family Pack", image: "/dogs/bella.jpg" }} size={48} />
        <span className="grow stack-0 left">
          <strong>Your account</strong>
          <span className="muted">Family · {dogs.length} {dogs.length === 1 ? "dog" : "dogs"} · 2 members</span>
        </span>
        <Icon name="chevronRight" size={20} className="muted" />
      </button>

      <div className="card card--list settings-list">
        {rows.map((r) => {
          const content = (
            <>
              <span className={`settings-icon tint-${r.tint}`}><Icon name={r.icon} size={20} /></span>
              <span className="grow stack-0 left">
                <strong>{r.label}</strong>
                <span className="muted small">{r.sub}</span>
              </span>
              <Icon name="chevronRight" size={18} className="muted" />
            </>
          );
          return r.to ? (
            <Link key={r.label} to={r.to} className="settings-row">{content}</Link>
          ) : (
            <button key={r.label} type="button" className="settings-row"
              onClick={() => showToast(`${r.label} isn't in the mockup yet`)}>{content}</button>
          );
        })}
      </div>
      <p className="muted tiny center">PawCoach 0.1 · {connection}</p>
    </div>
  );
}
