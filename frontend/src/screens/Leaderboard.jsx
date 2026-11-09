import { useEffect, useState } from "react";
import { Avatar, Segmented } from "../components/ui.jsx";
import { LB_CATEGORIES, LB_SCOPES } from "../data/mock.js";
import { useStore } from "../store.jsx";

const STEP_HEIGHT = { 1: 120, 2: 92, 3: 76 };

function moveText(move) {
  if (move?.startsWith("+")) return { text: `▲${move.slice(1)}`, tone: "up" };
  if (move?.startsWith("-")) return { text: `▼${move.slice(1)}`, tone: "down" };
  return { text: "–", tone: "same" };
}

export default function Leaderboard() {
  const { repository, showToast } = useStore();
  const [scope, setScope] = useState("city");
  const [category, setCategory] = useState("score");
  const [entries, setEntries] = useState([]);

  useEffect(() => {
    let mounted = true;
    async function fetchLeaderboard() {
      try {
        const data = await repository.getLeaderboard(category, scope);
        if (mounted) setEntries(data);
      } catch (err) {
        console.warn("Failed to load leaderboard:", err);
      }
    }
    fetchLeaderboard();
    return () => { mounted = false; };
  }, [category, scope, repository]);

  if (!entries || entries.length < 3) {
    return <div className="screen"><p className="muted center">Loading leaderboard…</p></div>;
  }

  const podium = [entries[1], entries[0], entries[2]];
  const me = entries.find((e) => e.mine) || entries[0];
  const n = me.move ? me.move.slice(1) : "";
  const meNote = me.move?.startsWith("+") ? `Up ${n} places this week`
    : me.move?.startsWith("-") ? `Down ${n} places this week` : "Same place as last week";

  return (
    <div className="screen">
      <header className="stack-4">
        <span className="eyebrow">This week · Nov 2–8</span>
        <h1 className="h1-tight">Who's the goodest boy?</h1>
      </header>

      <Segmented label="Area" options={LB_SCOPES} value={scope} onChange={setScope} />

      <div className="chips chips--scroll" role="group" aria-label="Category">
        {LB_CATEGORIES.map((c) => (
          <button key={c.id} type="button" className="chip-btn chip-btn--white" aria-pressed={category === c.id}
            onClick={() => setCategory(c.id)}>
            {c.label}
          </button>
        ))}
      </div>

      <section className="podium" aria-label="Podium">
        {podium.map((e) => (
          <div key={e.id} className="podium-col">
            <Avatar dog={e} size={e.rank === 1 ? 72 : 58} ring={e.rank === 1 ? "#3B2F28" : "#FFFFFF"} />
            <strong>{e.name}</strong>
            <span className="muted tiny center">{e.breed}</span>
            <div className={`podium-step rank-${e.rank}`} style={{ height: STEP_HEIGHT[e.rank] }}>
              <span className="podium-rank">{e.rank}</span>
              <span className="podium-value">{e.value}</span>
            </div>
          </div>
        ))}
      </section>

      <div className="me-card">
        <Avatar dog={me} size={44} />
        <span className="grow stack-2">
          <strong>{me.name} is #{me.rank}</strong>
          <span className="me-note">{meNote}</span>
        </span>
        <strong className="me-value">{me.value}</strong>
      </div>

      <section className="card card--list" aria-label="Rest of the ranking">
        {entries.slice(3).map((e) => {
          const mv = moveText(e.move);
          return (
            <div key={e.id} className={`rank-row ${e.mine ? "is-mine" : ""}`}>
              <span className="rank-num">{e.rank}</span>
              <Avatar dog={e} size={38} />
              <span className="grow stack-0">
                <strong>{e.name}</strong>
                <span className="muted tiny">{e.breed} · {e.area}</span>
              </span>
              <span className={`move move--${mv.tone}`}>{mv.text}</span>
              <strong className="rank-value">{e.value}</strong>
            </div>
          );
        })}
      </section>

      <button type="button" className="link-btn" onClick={() => showToast("Score details aren't in the mockup yet")}>
        How is the score calculated?
      </button>
    </div>
  );
}
