// Live training session driven by the backend (server/main.py).
//
// Polls GET /api/status a few times a second and turns it into the same view the simulated
// session (useLiveSession.js) gives the Live screen: detected pose, running cue, hold progress,
// rep counter and the latest event message. Cues and treats are sent to the server.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { CUES, POSE_LABEL, playClick, speak } from "./useLiveSession.js";

const POLL_MS = 250;
const REPS = 10;
const POSE_NAME = { sitting: "Sit", lying: "Down", standing: "Stand" };

const REASON = {
  daily_limit: "daily treat limit reached",
  dog_daily_limit: "daily treat limit reached",
  schedule_limit: "schedule treat limit reached",
  schedule_interval: "learning schedule: too soon after the last treat",
  min_interval: "too soon after the last treat",
  feeder_error: "the feeder didn't respond",
  reward_disabled: "rewards are turned off",
};
const reasonText = (r) => REASON[r] ?? (r ? r.replace(/_/g, " ") : "no treat");

const eventKey = (e) => [e.type, e.ts, e.id, e.exercise_id, e.stage].join("|");

/** Message for one backend event, or null to skip it. */
function describe(e, ctx) {
  const name = (e.target && ctx.cueName(e.target)) || "";
  const ex = e.exercise_id ? (CUES[e.exercise_id]?.label ?? e.exercise_id) : name;
  switch (e.type) {
    case "command_success":
      return { kind: "good", text: `Nice! Reacted in ${(e.reaction_s ?? 0).toFixed(1)} s · ${e.treat ? "treat given" : reasonText(e.detail)}` };
    case "command_fail":
      return e.detail === "cancelled" ? { kind: "info", text: "Cue cancelled" }
        : { kind: "bad", text: `No reaction to “${name}” in ${ctx.timeoutS} s` };
    case "passive_capture":
      if ((e.detail ?? "").startsWith("silent")) return null;
      return { kind: "good", text: `Caught “${name}” on ${ctx.his} own · ${e.treat ? "treat given" : reasonText(e.detail)}` };
    case "level_up":
      return { kind: "good", text: `Level up! “${ex}” is now a ${e.hold_s} s hold` };
    case "level_down":
      return { kind: "info", text: `“${ex}” back to a ${e.hold_s} s hold` };
    case "stage_up":
      return e.stage === "mastered" ? { kind: "good", text: `“${ex}” mastered!` }
        : e.stage === "train" ? { kind: "good", text: `“${ex}” learned · now training on cue` } : null;
    default:
      return null;                                     // command_rejected, highlight...
  }
}

/**
 * @param {object} opts
 * @param {object} opts.dog       the dog shown in Live (store shape, with apiId)
 * @param {() => void} opts.onChange  called after treats / results, to refresh the dog numbers
 */
export function useApiLiveSession({ dog, onChange }) {
  const [status, setStatus] = useState(null);
  const [online, setOnline] = useState(true);
  const [last, setLast] = useState(null);
  const [rep, setRep] = useState(0);
  const seen = useRef(null);                           // event keys already shown
  const lastCue = useRef(null);                        // the cue we sent (Sit vs Stay share a pose)
  const timeoutS = useRef(8);
  const ctxRef = useRef({});
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  ctxRef.current = {
    his: dog?.pronoun === "she" ? "her" : "his",
    timeoutS: timeoutS.current,
    cueName: (pose) => (lastCue.current?.pose === pose ? lastCue.current.label : POSE_NAME[pose]),
  };

  useEffect(() => {
    api.settings().then((s) => { timeoutS.current = s.active_command_timeout_s; }).catch(() => {});
  }, []);

  // Train the dog shown in the app.
  useEffect(() => {
    if (dog?.apiId != null) api.selectDog(dog.apiId).catch(() => {});
  }, [dog?.apiId]);

  useEffect(() => {
    let stop = false;
    let timer;
    const poll = async () => {
      try {
        const st = await api.status();
        if (stop) return;
        setOnline(true);
        setStatus(st);
        const events = [...(st.recent_events ?? [])].reverse();          // oldest first
        if (seen.current === null) {
          seen.current = new Set(events.map(eventKey));                  // don't replay old events
        } else {
          let changed = false;
          for (const e of events) {
            const key = eventKey(e);
            if (seen.current.has(key)) continue;
            seen.current.add(key);
            changed = true;
            const msg = describe(e, ctxRef.current);
            if (!msg) continue;
            if (e.treat && (e.type === "command_success" || e.type === "passive_capture")
              && st.mode === "mock") playClick();                         // the device speaker clicks in camera mode
            setLast(msg);
          }
          if (changed) onChangeRef.current?.();
        }
      } catch {
        if (!stop) setOnline(false);
      }
      if (!stop) timer = setTimeout(poll, POLL_MS);
    };
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, []);

  const giveCue = useCallback(async (cueId) => {
    const cue = CUES[cueId];
    try {
      await api.command(cueId);
    } catch (err) {
      return { ok: false, reason: err.status === 409 ? "busy" : err.message };
    }
    lastCue.current = cue;
    setRep((r) => (r % REPS) + 1);
    setLast({ kind: "info", text: `Cue: “${cue.label}!”` });
    if (status?.mode === "mock") speak(`${cue.label}!`);                 // camera mode: the device says it
    return { ok: true };
  }, [status?.mode]);

  const giveTreat = useCallback(async () => {
    try {
      const r = await api.treat();
      setLast(r.ok ? { kind: "good", text: "Treat given" } : { kind: "bad", text: `No treat: ${reasonText(r.reason)}` });
      onChangeRef.current?.();
    } catch {
      setLast({ kind: "bad", text: "Couldn't reach the feeder" });
    }
  }, []);

  const logEvent = useCallback((kind, text) => setLast({ kind, text }), []);

  // ---- view (same fields as the simulated session)
  const b = status?.behavior ?? {};
  const state = status?.posture?.state;
  const pose = state && POSE_LABEL[state] ? state : null;
  const activeCue = b.mode === "command"
    ? { ...(CUES[b.exercise_id] ?? lastCue.current ?? CUES.sit), holdS: b.hold_s ?? 1 }
    : null;
  const holdS = activeCue?.holdS ?? 0;
  const heldS = activeCue && state === b.target ? Math.min(status.posture.held_s, holdS) : 0;
  const session = status?.session;

  return {
    online,
    mode: status?.mode ?? null,
    dogId: status?.dog?.id ?? null,
    treatsToday: status?.treats_today ?? dog?.treatsToday ?? 0,
    treatLimit: status?.daily_limit ?? dog?.treatLimit ?? 0,
    pose,
    poseLabel: pose ? POSE_LABEL[pose] : state === "undefined" ? "Unsure" : null,
    confidence: status?.frame_posture?.confidence ?? 0,
    activeCue,
    heldS,
    holdS,
    rep: session ? session.rep : rep,
    reps: session ? session.reps : REPS,
    last,
    giveCue,
    giveTreat,
    logEvent,
  };
}
