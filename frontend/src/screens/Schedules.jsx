import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { Avatar, BackLink, Segmented, Stepper, Toggle } from "../components/ui.jsx";
import { useStore } from "../store.jsx";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function AddScheduleModal({ open, onClose, dogs, defaultDogId }) {
  const { addSchedule } = useStore();
  const [dogId, setDogId] = useState(defaultDogId || dogs[0]?.id || "1");
  const [kind, setKind] = useState("learn");
  const [selectedExercises, setSelectedExercises] = useState(["sit"]);
  const [selectedDays, setSelectedDays] = useState([0, 1, 2, 3, 4, 5, 6]);
  const [start, setStart] = useState("10:00");
  const [end, setEnd] = useState("17:00");
  const [trainTimes, setTrainTimes] = useState(["09:00", "18:00"]);
  const [newTimeInput, setNewTimeInput] = useState("12:00");
  const [maxTreats, setMaxTreats] = useState(10);
  const [reps, setReps] = useState(10);
  const [intervalMin, setIntervalMin] = useState(30);

  if (!open) return null;

  const toggleDay = (d) => {
    setSelectedDays((prev) =>
      prev.includes(d) ? (prev.length > 1 ? prev.filter((x) => x !== d) : prev) : [...prev, d].sort()
    );
  };

  const toggleExercise = (ex) => {
    setSelectedExercises((prev) =>
      prev.includes(ex) ? (prev.length > 1 ? prev.filter((x) => x !== ex) : prev) : [...prev, ex]
    );
  };

  const addTimeSlot = () => {
    if (!newTimeInput || trainTimes.includes(newTimeInput)) return;
    setTrainTimes([...trainTimes, newTimeInput].sort());
  };

  const removeTimeSlot = (t) => {
    if (trainTimes.length <= 1) return;
    setTrainTimes(trainTimes.filter((x) => x !== t));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const dog = dogs.find((d) => String(d.id) === String(dogId)) || dogs[0];
    const whenFormatted =
      kind === "learn"
        ? `${selectedDays.length === 7 ? "Daily" : selectedDays.map((d) => DAY_LABELS[d]).join(", ")}, ${start}–${end}`
        : `${selectedDays.length === 7 ? "Daily" : selectedDays.map((d) => DAY_LABELS[d]).join(", ")}, ${trainTimes.join(" and ")}`;

    const title = `${dog.name} · ${selectedExercises.map((x) => x.charAt(0).toUpperCase() + x.slice(1)).join(" & ")}`;

    const success = await addSchedule({
      dog_id: dog.apiId ?? dog.id,
      dog: String(dog.id),
      kind,
      type: kind,
      title,
      when: whenFormatted,
      exercise_ids: selectedExercises,
      days: selectedDays,
      start: kind === "learn" ? start : null,
      end: kind === "learn" ? end : null,
      times: kind === "train" ? trainTimes : [],
      reps,
      max: maxTreats,
      max_treats: maxTreats,
      intervalMin,
      min_interval_s: intervalMin * 60,
    });

    if (success) onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Add a schedule">
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>New Schedule</h2>
          <button type="button" className="icon-btn icon-btn--sm" onClick={onClose} aria-label="Close">
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="stack-14">
          {/* Target Dog Selector */}
          <div className="form-field">
            <label>Dog</label>
            <div className="chips">
              {dogs.map((d, idx) => {
                const isFirst = idx === 0;
                /* CONDITIONAL RENDERING: First dog is active; other dogs are disabled with 'To be continued' */
                return (
                  <button
                    key={d.id}
                    type="button"
                    className={`chip-btn ${dogId === String(d.id) ? "is-selected" : ""} ${!isFirst ? "is-disabled" : ""}`}
                    aria-pressed={dogId === String(d.id)}
                    disabled={!isFirst}
                    style={!isFirst ? { opacity: 0.5, cursor: "not-allowed" } : undefined}
                    onClick={() => {
                      if (isFirst) setDogId(String(d.id));
                    }}
                  >
                    {d.name} {!isFirst && "(To be continued)"}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Schedule Kind */}
          <div className="form-field">
            <label>Schedule Type</label>
            <Segmented
              label="Schedule Type"
              value={kind}
              onChange={setKind}
              options={[
                ["learn", "Learning (Passive)"],
                ["train", "Training (On cue)"],
              ]}
            />
          </div>

          {/* Exercises */}
          <div className="form-field">
            <label>Exercises</label>
            <div className="chips">
              {["sit", "down", "stand", "stay"].map((ex) => (
                <button
                  key={ex}
                  type="button"
                  className="chip-btn"
                  aria-pressed={selectedExercises.includes(ex)}
                  onClick={() => toggleExercise(ex)}
                >
                  {ex.charAt(0).toUpperCase() + ex.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Days of week */}
          <div className="form-field">
            <label>Active Days</label>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {DAY_LABELS.map((lbl, idx) => (
                <button
                  key={lbl}
                  type="button"
                  className="chip-btn"
                  style={{ minWidth: 42, padding: "0 8px", fontSize: 13 }}
                  aria-pressed={selectedDays.includes(idx)}
                  onClick={() => toggleDay(idx)}
                >
                  {lbl}
                </button>
              ))}
            </div>
          </div>

          {/* Timing details */}
          {kind === "learn" ? (
            <div className="stack-10">
              <div className="form-row-2">
                <div className="form-field">
                  <label htmlFor="sched-start">Window start</label>
                  <input
                    id="sched-start"
                    type="time"
                    className="text-input"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                  />
                </div>
                <div className="form-field">
                  <label htmlFor="sched-end">Window end</label>
                  <input
                    id="sched-end"
                    type="time"
                    className="text-input"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                  />
                </div>
              </div>
              <div className="form-field">
                <label>Minimum treat spacing</label>
                <div className="row-between card" style={{ padding: "8px 12px" }}>
                  <span className="small">Every {intervalMin} minutes</span>
                  <Stepper
                    value={intervalMin}
                    min={5}
                    max={120}
                    label="minutes"
                    onChange={(v) => setIntervalMin(v)}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="stack-10">
              <div className="form-field">
                <label>Session times</label>
                <div className="chips">
                  {trainTimes.map((t) => (
                    <span key={t} className="pill pill--honey" style={{ gap: 6, display: "inline-flex" }}>
                      {t}
                      {trainTimes.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeTimeSlot(t)}
                          style={{ border: 0, background: "none", cursor: "pointer", padding: 0 }}
                        >
                          ✕
                        </button>
                      )}
                    </span>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                  <input
                    type="time"
                    className="text-input grow"
                    value={newTimeInput}
                    onChange={(e) => setNewTimeInput(e.target.value)}
                  />
                  <button type="button" className="btn btn--soft btn--sm" onClick={addTimeSlot}>
                    + Add time
                  </button>
                </div>
              </div>

              <div className="form-field">
                <label>Reps per session</label>
                <div className="row-between card" style={{ padding: "8px 12px" }}>
                  <span className="small">{reps} cues requested</span>
                  <Stepper value={reps} min={1} max={30} label="reps" onChange={(v) => setReps(v)} />
                </div>
              </div>
            </div>
          )}

          {/* Max treats limit */}
          <div className="form-field">
            <label>Max treats</label>
            <div className="row-between card" style={{ padding: "8px 12px" }}>
              <span className="small">Limit per session / window</span>
              <Stepper value={maxTreats} min={1} max={50} label="treats" onChange={(v) => setMaxTreats(v)} />
            </div>
          </div>

          <div className="btn-row" style={{ marginTop: 8 }}>
            <button type="button" className="btn btn--soft" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--honey grow-2">
              Save schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Schedules() {
  const { schedules, dogs, getDog, updateSchedule, deleteSchedule } = useStore();
  const [filter, setFilter] = useState("all");
  const [showInfo, setShowInfo] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  const firstDog = dogs[0];

  const perDay = Object.fromEntries(dogs.map((d) => [d.id, 0]));
  schedules.forEach((s) => {
    if (s.on) {
      const dogId = s.dog;
      if (perDay[dogId] !== undefined) {
        perDay[dogId] += s.max * s.sessions;
      }
    }
  });

  const visible = schedules.filter((s) => filter === "all" || s.type === filter);

  return (
    <div className="screen">
      <div className="row-between">
        <BackLink to="/settings" label="Settings" />
        {/* Info button in top right */}
        <button
          type="button"
          className="icon-btn"
          aria-label="What do these labels mean?"
          aria-expanded={showInfo}
          onClick={() => setShowInfo((v) => !v)}
          style={{ background: showInfo ? "var(--honey-soft)" : "var(--surface)" }}
        >
          <Icon name="info" size={20} strokeWidth={2.2} />
        </button>
      </div>

      <header className="stack-6">
        <h1>Schedules</h1>
        <p className="lead">
          Automated training routines with strict treat limits to keep practice fun and safe.
        </p>
      </header>

      {/* CONDITIONAL RENDERING: Expandable top-right Info banner using native theme styling without emojis */}
      {showInfo && (
        <section
          className="card stack-12"
          style={{
            animation: "sheetUp 0.18s ease-out",
          }}
        >
          <div className="row-between">
            <h2>Schedule Concepts &amp; Guide</h2>
            <button
              type="button"
              className="icon-btn icon-btn--sm"
              onClick={() => setShowInfo(false)}
              aria-label="Close guide"
              style={{ background: "var(--soft)" }}
            >
              <Icon name="x" size={16} />
            </button>
          </div>
          <div className="stack-10">
            {/* Learning block: peach/soft terracotta block */}
            <div className="card card--peach stack-4" style={{ borderRadius: 16 }}>
              <div className="row-between">
                <span className="eyebrow" style={{ color: "#A8432F" }}>Learning (Passive capture)</span>
                <span className="pill tiny" style={{ background: "var(--surface)", color: "#7A2E17", fontWeight: 800 }}>Passive</span>
              </div>
              <p className="small" style={{ color: "var(--ink-2)", lineHeight: 1.45 }}>
                The AI camera watches your dog naturally. When they perform a target behavior by themselves (like lying down or sitting), the feeder clicks and rewards them with a treat to link the action to the cue word.
              </p>
            </div>

            {/* Training block: honey/warm yellow block */}
            <div className="card card--honey stack-4" style={{ borderRadius: 16 }}>
              <div className="row-between">
                <span className="eyebrow" style={{ color: "var(--honey-ink)" }}>Training (Active sessions)</span>
                <span className="pill tiny" style={{ background: "var(--surface)", color: "var(--honey-ink)", fontWeight: 800 }}>On cue</span>
              </div>
              <p className="small" style={{ color: "var(--honey-ink)", lineHeight: 1.45 }}>
                Automatic cue sessions scheduled at specific times of the day. The device calls the command and guides your dog through repetitions.
              </p>
            </div>

            {/* Max treats block: sage/soft green block */}
            <div className="card card--sage stack-4" style={{ borderRadius: 16 }}>
              <div className="row-between">
                <span className="eyebrow" style={{ color: "var(--sage-ink)" }}>Max treats limit</span>
                <span className="pill tiny" style={{ background: "var(--surface)", color: "var(--sage-ink)", fontWeight: 800 }}>Safety cap</span>
              </div>
              <p className="small" style={{ color: "var(--sage-deep)", lineHeight: 1.45 }}>
                The maximum number of treats the feeder will dispense during a single learning window or training session. Once this limit is reached, it automatically stops dispensing, even if the time window hasn't ended.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Treats per day summary */}
      <section className="card stack-10" aria-label="Treats per day from schedules">
        <strong>Treats per day, from schedules</strong>
        <div className="totals">
          {dogs.map((d, idx) => {
            const isFirst = idx === 0;
            return (
              <div
                key={d.id}
                className="total"
                style={!isFirst ? { opacity: 0.5 } : undefined}
              >
                <strong>{perDay[d.id] ?? 0}</strong>
                <span className="muted small">
                  {d.name} {!isFirst && <span className="tiny">(TBC)</span>}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      <Segmented
        label="Filter"
        value={filter}
        onChange={setFilter}
        options={[
          ["all", "All"],
          ["learn", "Learning"],
          ["train", "Training"],
        ]}
      />

      <div className="stack-10">
        {visible.map((s) => {
          const dog = getDog(s.dog);
          const isFirstDog = firstDog && String(s.dog) === String(firstDog.id);
          const learn = s.type === "learn";

          /* CONDITIONAL RENDERING: If schedule belongs to other dogs than the first dog, render as disabled & non-interactable */
          if (!isFirstDog) {
            return (
              <div
                key={s.id}
                className="card stack-12 schedule is-off is-disabled"
                aria-disabled="true"
                style={{ opacity: 0.55, cursor: "not-allowed" }}
              >
                <div className="schedule-head">
                  <Avatar dog={dog} size={40} />
                  <div className="grow stack-2">
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <strong className="schedule-title">{s.title}</strong>
                      <span className="pill" style={{ fontSize: 10, padding: "1px 6px", background: "var(--soft)" }}>
                        To be continued
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <span className="pill tiny" style={{ background: learn ? "var(--peach-soft)" : "var(--honey-soft)" }}>
                        {learn ? "Learning" : `Training · ${s.reps ?? 10} reps`}
                      </span>
                      <span className="small muted">{s.when}</span>
                    </div>
                  </div>
                  <Toggle on={false} disabled onChange={() => {}} label={`${s.title} (disabled)`} />
                </div>
                <div className="limit-row">
                  <span className="small strong">Max treats: {s.max}</span>
                  <span className="muted tiny">Demo preview</span>
                </div>
              </div>
            );
          }

          /* CONDITIONAL RENDERING: First dog schedule is fully interactive without repeating verbose descriptions */
          return (
            <div key={s.id} className={`card stack-12 schedule ${s.on ? "" : "is-off"}`}>
              <div className="schedule-head">
                <Avatar dog={dog} size={40} />
                <div className="grow stack-2">
                  <strong className="schedule-title">{s.title}</strong>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                    <span
                      className="pill tiny"
                      style={{
                        background: learn ? "var(--peach-soft)" : "var(--honey-soft)",
                        color: learn ? "#7A2E17" : "var(--honey-ink)",
                        fontWeight: 800,
                      }}
                    >
                      {learn ? "Learning" : `Training · ${s.reps ?? 10} reps`}
                    </span>
                    <span className="small strong">{s.when}</span>
                  </div>
                </div>
                <Toggle
                  on={s.on}
                  label={`${s.on ? "Turn off" : "Turn on"} ${s.title}`}
                  onChange={(on) => updateSchedule(s.id, { on })}
                />
              </div>

              <div className="limit-row">
                <span className="stack-0">
                  <span className="small strong">Max treats</span>
                  <span className="muted tiny">
                    {learn
                      ? `${s.intervalMin ?? 30}m spacing`
                      : s.sessions > 1
                      ? `${s.sessions} sessions/day`
                      : "per session"}
                  </span>
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Stepper
                    value={s.max}
                    label="treats"
                    onChange={(max) => updateSchedule(s.id, { max })}
                  />
                  <button
                    type="button"
                    className="icon-btn icon-btn--sm"
                    aria-label={`Delete schedule ${s.title}`}
                    onClick={() => deleteSchedule(s.id)}
                    style={{ background: "var(--soft)", color: "var(--danger)" }}
                  >
                    <Icon name="trash" size={16} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        className="btn btn--honey btn--block"
        onClick={() => setShowAddModal(true)}
      >
        + New schedule
      </button>

      <AddScheduleModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        dogs={dogs}
        defaultDogId={firstDog?.id}
      />
    </div>
  );
}
