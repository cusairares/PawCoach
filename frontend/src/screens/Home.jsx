import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { Link } from "../router.jsx";
import { useStore } from "../store.jsx";

function today() {
  return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

export default function Home() {
  const { dogs, week: weekAll, showToast } = useStore();
  const [filter, setFilter] = useState("all");
  const selected = dogs.find((d) => d.id === filter);
  const week = selected ? selected.week : weekAll.values;
  const labels = (selected?.weekLabels) ?? weekAll.labels;
  const avg = Math.round(week[week.length - 1] ?? 0);

  return (
    <div className="screen">
      <header className="screen-header">
        <div>
          <span className="eyebrow-muted">{today()}</span>
          <h1>My dogs</h1>
        </div>
        <button type="button" className="icon-btn" aria-label="Add a dog" onClick={() => showToast("Adding dogs isn't in the mockup yet")}>
          <Icon name="plus" size={20} strokeWidth={2.2} />
        </button>
      </header>

      <section className="stack-12" aria-label="My dogs">
        {dogs.map((d) => (
          <Link key={d.id} to={`/dogs/${d.id}`} className="card dog-row">
            <Avatar dog={d} size={56} />
            <span className="dog-row-text">
              <strong>{d.name}</strong>
              <span className="muted">{d.breed} · {d.age}</span>
              <span className="good small">{d.successesToday} successes today · {d.treatsToday} treats</span>
            </span>
            <Icon name="chevronRight" size={20} className="muted" />
          </Link>
        ))}
      </section>

      <section className="card stack-14" aria-labelledby="week-h">
        <div className="row-between">
          <h2 id="week-h">This week</h2>
          <span className="good strong">{avg}% success</span>
        </div>
        <div className="chips" role="group" aria-label="Filter by dog">
          {[["all", "All"], ...dogs.map((d) => [d.id, d.name])].map(([id, label]) => (
            <button key={id} type="button" className="chip-btn" aria-pressed={filter === id} onClick={() => setFilter(id)}>
              {label}
            </button>
          ))}
        </div>
        <div className="bars" role="img" aria-label={`Success rate this week, ending at ${avg}% today`}>
          {week.map((v, i) => (
            <div key={i} className="bar-col">
              <span className="bar-value">{v}%</span>
              <div className={`bar ${i === week.length - 1 ? "is-today" : ""}`} style={{ height: `${v * 1.2}px` }} />
              <span className={`bar-label ${i === week.length - 1 ? "is-today" : ""}`}>{labels[i]}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
