import Icon from "./Icon.jsx";
import { Link } from "../router.jsx";

const ITEMS = [
  { id: "home", to: "/home", label: "Home", icon: "home" },
  { id: "moments", to: "/moments", label: "Moments", icon: "moments" },
  { id: "live", to: "/live", label: "Live", icon: "live", raised: true },
  { id: "leaderboard", to: "/leaderboard", label: "Leaderboard", icon: "trophy" },
  { id: "settings", to: "/settings", label: "Settings", icon: "settings" },
];

export default function BottomNav({ active }) {
  return (
    <nav className="bottom-nav" aria-label="Main menu">
      {ITEMS.map((it) => {
        const on = it.id === active;
        return (
          <Link key={it.id} to={it.to} className={`nav-item ${on ? "is-active" : ""} ${it.raised ? "is-raised" : ""}`}
            aria-current={on ? "page" : undefined}>
            <span className="nav-icon">
              <Icon name={it.icon} size={it.raised ? 24 : 22} strokeWidth={it.raised ? 2 : 1.9} />
            </span>
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}
