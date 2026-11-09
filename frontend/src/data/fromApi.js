// Turns backend data (snake_case, see server/main.py) into the shapes the screens use
// (the same shapes as data/mock.js, so the screens work with both).
import { AVATAR, DOGS as MOCK_DOGS } from "./mock.js";

const DAY_LETTER = ["S", "M", "T", "W", "T", "F", "S"];           // Date.getDay(): 0 = Sunday
const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; // backend: 0 = Monday

// The leaderboard needs a shared online service that doesn't exist yet,
// so the score / rank / city still come from the mock data (matched by name).
const COMMUNITY = Object.fromEntries(MOCK_DOGS.map((d) => [d.name, { score: d.score, rank: d.rank, city: d.city }]));

const pct = (rate) => (rate == null ? 0 : Math.round(rate * 100));
const fmtS = (s) => `${Number.isInteger(s) ? s : s.toFixed(1)} s`;

export function hhmm(ts) {
  return new Date(ts * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function ago(ts) {
  if (!ts) return null;
  const days = Math.floor((Date.now() - ts * 1000) / 86_400_000);
  if (days <= 0) return "today";
  return days === 1 ? "yesterday" : `${days} days ago`;
}

function age(birthDate) {
  if (!birthDate) return "";
  const b = new Date(birthDate);
  const now = new Date();
  const months = (now.getFullYear() - b.getFullYear()) * 12 + now.getMonth() - b.getMonth();
  if (months < 12) return `${Math.max(1, months)} mos`;
  const years = Math.floor(months / 12);
  return `${years} ${years === 1 ? "yr" : "yrs"}`;
}

/** Day labels (M, T, W...) for rows from /stats/daily or a dog's `week`. */
export const weekLabels = (rows) => rows.map((r) => DAY_LETTER[new Date(`${r.date}T12:00`).getDay()]);
/** Success % per day (0 on days without commands). */
export const weekValues = (rows) => rows.map((r) => pct(r.success_rate));

function formatDays(days) {
  const set = [...days].sort((a, b) => a - b).join(",");
  if (set === "0,1,2,3,4,5,6") return "Daily";
  if (set === "0,1,2,3,4") return "Mon–Fri";
  if (set === "5,6") return "Weekends";
  return days.map((d) => DAY_SHORT[d]).join(", ");
}

function joinAnd(items) {
  return items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function scheduleWhen(s) {
  return s.kind === "learn"
    ? `${formatDays(s.days)}, ${s.start}–${s.end}`
    : `${formatDays(s.days)}, ${joinAnd(s.times)}`;
}

function limitNote(s) {
  const minutes = Math.round(s.min_interval_s / 60);
  return `max ${s.max_treats} treats${minutes ? ` · one every ${minutes} min` : ""}`;
}

function exerciseDetail(p, dog, names) {
  if (p.stage === "mastered") return "Mastered · quick refresher weekly";
  if (p.stage === "train") {
    if (p.max_hold_s >= 10) return `Holds ${fmtS(p.hold_s)} · goal ${fmtS(p.max_hold_s)}`;
    if (p.level === p.levels - 1) return `Holds ${fmtS(p.hold_s)} · one more level to master it`;
    return `Holds ${fmtS(p.hold_s)}`;
  }
  if (p.requires) return `Starts once ${dog.pronoun} masters “${names[p.requires] ?? p.requires}”`;
  if (!p.detectable) return "The camera can't recognize this one yet";
  return "Not started yet";
}

function toExercise(p, dog, learnSchedule, names) {
  const his = dog.pronoun === "she" ? "her" : "his";
  return {
    id: p.exercise_id,
    name: p.name,
    pose: p.pose,
    stage: p.stage,
    moments: p.moments,
    goal: p.moments_goal,
    startedAgo: ago(p.started_at),
    schedule: learnSchedule ? scheduleWhen(learnSchedule) : "No learning schedule yet",
    limitNote: learnSchedule ? limitNote(learnSchedule) : "Add one in Settings › Schedules",
    caught: (dog.caught_today ?? [])
      .filter((c) => c.target === p.pose)
      .map((c) => [hhmm(c.ts), `Did it on ${his} own${c.treat ? "" : " · no treat (limit)"}`]),
    rate: pct(p.success_rate),
    level: p.level,
    detail: exerciseDetail(p, dog, names),
  };
}

/** One dog from GET /api/dogs, plus the schedules (for the learning windows). */
export function toDog(d, schedules) {
  const names = Object.fromEntries(d.exercises.map((p) => [p.exercise_id, p.name]));
  const community = COMMUNITY[d.name] ?? {};
  const learnFor = (exId) => schedules.find((s) => s.dog_id === d.id && s.kind === "learn" && s.enabled
    && s.exercise_ids.includes(exId)) ?? schedules.find((s) => s.dog_id === d.id && s.kind === "learn"
    && s.exercise_ids.includes(exId));
  return {
    id: String(d.id),
    apiId: d.id,
    name: d.name,
    pronoun: d.pronoun ?? "he",
    initial: d.name.charAt(0).toUpperCase(),
    color: d.color || AVATAR.honey,
    breed: d.breed || "Mixed breed",
    age: age(d.birth_date),
    weight: d.weight_kg ? `${d.weight_kg} kg` : "",
    score: community.score ?? null,
    rank: community.rank ?? null,
    city: community.city ?? null,
    streak: d.streak_days,
    success7d: pct(d.success_rate_7d),
    reaction: d.avg_reaction_s ? `${d.avg_reaction_s.toFixed(1)} s` : "–",
    successesToday: d.successes_today,
    treatsToday: d.treats_today,
    treatLimit: d.daily_treat_limit,
    week: weekValues(d.week),
    weekLabels: weekLabels(d.week),
    exercises: d.exercises.map((p) => toExercise(p, d, learnFor(p.exercise_id), names)),
  };
}

/** One schedule from GET /api/schedules, in the Schedules screen's shape. */
export function toSchedule(s, apiDogs) {
  const dog = apiDogs.find((d) => d.id === s.dog_id);
  const names = Object.fromEntries((dog?.exercises ?? []).map((p) => [p.exercise_id, p.name]));
  return {
    id: s.id,
    dog: String(s.dog_id),
    type: s.kind,
    title: `${dog?.name ?? "?"} · ${joinAnd(s.exercise_ids.map((e) => names[e] ?? e))}`,
    when: scheduleWhen(s),
    sessions: s.kind === "train" ? s.times.length : 1,
    max: s.max_treats,
    reps: s.reps,
    intervalMin: Math.round(s.min_interval_s / 60),
    on: s.enabled,
  };
}
