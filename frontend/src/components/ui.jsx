// Small shared UI pieces.
import Icon from "./Icon.jsx";
import { Link } from "../router.jsx";

export function Avatar({ dog, size = 48, ring }) {
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: Math.round(size / 2.5),
      background: dog.color, boxShadow: ring ? `0 0 0 3px ${ring}` : undefined }}>
      {dog.initial ?? dog.name[0]}
    </span>
  );
}

export function BackLink({ to, label }) {
  return (
    <Link to={to} className="back-link">
      <Icon name="chevronLeft" size={20} strokeWidth={2.2} />
      {label}
    </Link>
  );
}

export function Toggle({ on, onChange, label }) {
  return (
    <button type="button" className={`toggle ${on ? "is-on" : ""}`} aria-pressed={on} aria-label={label}
      onClick={() => onChange(!on)}>
      <span className="toggle-knob" />
    </button>
  );
}

export function Stepper({ value, onChange, min = 1, max = 30, label = "value" }) {
  return (
    <div className="stepper">
      <button type="button" aria-label={`Decrease ${label}`} onClick={() => onChange(Math.max(min, value - 1))}>−</button>
      <strong>{value}</strong>
      <button type="button" aria-label={`Increase ${label}`} onClick={() => onChange(Math.min(max, value + 1))}>+</button>
    </div>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="seg" role="group" aria-label={label} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map(([id, text]) => (
        <button key={id} type="button" aria-pressed={value === id} onClick={() => onChange(id)}>{text}</button>
      ))}
    </div>
  );
}

export function StatusPill({ online }) {
  return (
    <span className={`status-pill ${online ? "" : "is-off"}`}>
      <span className="dot" />
      {online ? "Online" : "Offline"}
    </span>
  );
}

export function Pips({ level, total = 6 }) {
  return (
    <div className="pips" aria-label={`Level ${level} of ${total}`}>
      {Array.from({ length: total }, (_, i) => <span key={i} className={i < level ? "on" : ""} />)}
    </div>
  );
}

export function Progress({ value, tone = "honey", thick }) {
  return (
    <div className={`progress ${thick ? "thick" : ""} tone-${tone}`}>
      <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
