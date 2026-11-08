import { useState } from "react";
import { Avatar, BackLink, Segmented, Stepper, Toggle } from "../components/ui.jsx";
import { useStore } from "../store.jsx";

export default function Schedules() {
  const { schedules, dogs, getDog, updateSchedule, showToast } = useStore();
  const [filter, setFilter] = useState("all");

  const perDay = Object.fromEntries(dogs.map((d) => [d.id, 0]));
  schedules.forEach((s) => { if (s.on) perDay[s.dog] += s.max * s.sessions; });
  const visible = schedules.filter((s) => filter === "all" || s.type === filter);

  return (
    <div className="screen">
      <BackLink to="/settings" label="Settings" />
      <header className="stack-6">
        <h1>Schedules</h1>
        <p className="lead">Every schedule has a treat limit. Once it's reached, it stops on its own, even if the time window isn't over.</p>
      </header>

      <section className="card stack-10" aria-label="Treats per day from schedules">
        <strong>Treats per day, from schedules</strong>
        <div className="totals">
          {dogs.map((d) => (
            <div key={d.id} className="total">
              <strong>{perDay[d.id]}</strong>
              <span className="muted small">{d.name}</span>
            </div>
          ))}
        </div>
      </section>

      <Segmented label="Filter" value={filter} onChange={setFilter}
        options={[["all", "All"], ["learn", "Learning"], ["train", "Training"]]} />

      <div className="stack-10">
        {visible.map((s) => {
          const learn = s.type === "learn";
          return (
            <div key={s.id} className={`card stack-12 schedule ${s.on ? "" : "is-off"}`}>
              <div className="schedule-head">
                <Avatar dog={getDog(s.dog)} size={40} />
                <div className="grow stack-2">
                  <strong className="schedule-title">{s.title}</strong>
                  <span className="muted-2 small">
                    {learn ? "Learning: rewarded when it happens on its own" : "Training: gets the cue · 10 reps"}
                  </span>
                  <span className="small strong">{s.when}</span>
                </div>
                <Toggle on={s.on} label={`${s.on ? "Turn off" : "Turn on"} ${s.title}`}
                  onChange={(on) => updateSchedule(s.id, { on })} />
              </div>
              <div className="limit-row">
                <span className="stack-0">
                  <span className="small strong">Max treats</span>
                  <span className="muted tiny">
                    {learn ? "at most one every 30 min" : s.sessions > 1 ? `per session · ${s.sessions} sessions a day` : "per session"}
                  </span>
                </span>
                <Stepper value={s.max} label="treats" onChange={(max) => updateSchedule(s.id, { max })} />
              </div>
            </div>
          );
        })}
      </div>

      <button type="button" className="btn btn--honey btn--block" onClick={() => showToast("New schedules aren't in the mockup yet")}>
        + New schedule
      </button>
    </div>
  );
}
