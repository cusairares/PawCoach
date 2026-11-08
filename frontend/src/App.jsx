import BottomNav from "./components/BottomNav.jsx";
import { match, useRoute } from "./router.jsx";
import { useStore } from "./store.jsx";
import Home from "./screens/Home.jsx";
import Moments from "./screens/Moments.jsx";
import Live from "./screens/Live.jsx";
import Leaderboard from "./screens/Leaderboard.jsx";
import Settings from "./screens/Settings.jsx";
import Dog from "./screens/Dog.jsx";
import Exercise from "./screens/Exercise.jsx";
import Schedules from "./screens/Schedules.jsx";
import Feeder from "./screens/Feeder.jsx";
import Camera from "./screens/Camera.jsx";

// [pattern, component, active bottom-nav tab]
const ROUTES = [
  ["/home", Home, "home"],
  ["/moments", Moments, "moments"],
  ["/live", Live, "live"],
  ["/leaderboard", Leaderboard, "leaderboard"],
  ["/settings", Settings, "settings"],
  ["/settings/schedules", Schedules, "settings"],
  ["/settings/feeder", Feeder, "settings"],
  ["/settings/camera", Camera, "settings"],
  ["/dogs/:dogId", Dog, "home"],
  ["/dogs/:dogId/exercises/:exerciseId", Exercise, "home"],
];

function resolve(path) {
  for (const [pattern, Component, tab] of ROUTES) {
    const params = match(pattern, path);
    if (params) return { Component, tab, params };
  }
  return { Component: Home, tab: "home", params: {} };
}

export default function App() {
  const path = useRoute();
  const { toast } = useStore();
  const { Component, tab, params } = resolve(path);

  return (
    <div className="app-shell">
      <div className="phone">
        <main className="screen-area">
          <Component {...params} />
        </main>
        <BottomNav active={tab} />
        {toast && <div className="toast" role="status">{toast}</div>}
      </div>
    </div>
  );
}
