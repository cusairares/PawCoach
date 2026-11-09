// Live training session — SIMULATED in the browser for the prototype.
//
// It mimics what the backend's BehaviorController does (src/behavior.py):
//   cue -> wait for the dog to *transition into* the pose -> hold it -> success + treat,
//   or time out after `timeoutS`.
// When the backend gets an API, replace the simulation with real status polling
// (see BACKEND_QUESTIONS.md, Q1–Q4).
import { useCallback, useEffect, useRef, useState } from "react";

export const CUES = {
  sit: { id: "sit", label: "Sit", pose: "sitting", holdS: 1.0 },
  down: { id: "down", label: "Down", pose: "lying", holdS: 1.0 },
  stand: { id: "stand", label: "Stand", pose: "standing", holdS: 1.0 },
  stay: { id: "stay", label: "Stay", pose: "sitting", holdS: 1.0 },
};

export const POSE_LABEL = { sitting: "Sitting", standing: "Standing", lying: "Lying down" };
const POSES = ["sitting", "standing", "lying"];
const TICK_MS = 150;
const TIMEOUT_S = 8;
const REPS = 10;

const rand = (a, b) => a + Math.random() * (b - a);
const now = () => performance.now() / 1000;

export function speak(text) {
  try {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.95;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch { /* audio is optional */ }
}

let audioCtx;
export function playClick() {
  try {
    audioCtx ??= new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.06].forEach((offset) => {
      const t = audioCtx.currentTime + offset;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(2400, t);
      gain.gain.setValueAtTime(0.2, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.03);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.04);
    });
  } catch { /* audio is optional */ }
}

/**
 * @param {object} opts
 * @param {() => boolean} opts.onReward  called on success; returns true if a treat was dispensed
 */
export function useLiveSession({ onReward }) {
  const sim = useRef({
    pose: "sitting", confidence: 0.94, nextChange: now() + rand(6, 10),
    command: null, rep: 4, last: null,
  });
  const [view, setView] = useState(() => snapshot(sim.current, now()));
  const rewardRef = useRef(onReward);
  rewardRef.current = onReward;

  useEffect(() => {
    const id = setInterval(() => {
      const t = now();
      tick(sim.current, t, rewardRef);
      setView(snapshot(sim.current, t));
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  const giveCue = useCallback((cueId) => {
    const s = sim.current;
    const cue = CUES[cueId];
    const t = now();
    if (s.command) return false;                         // backend rejects a second command ("busy")
    if (s.pose === cue.pose) s.pose = cue.pose === "standing" ? "sitting" : "standing";
    const obeys = Math.random() > 0.15;                  // the dog sometimes ignores the cue
    s.command = { cue, startedAt: t, obeyAt: obeys ? t + rand(0.7, 2.2) : Infinity, holdStart: null };
    s.rep = (s.rep % REPS) + 1;
    s.last = { kind: "info", text: `Cue: “${cue.label}!”` };
    speak(`${cue.label}!`);
    setView(snapshot(s, t));
    return true;
  }, []);

  const logEvent = useCallback((kind, text) => {
    sim.current.last = { kind, text };
    setView(snapshot(sim.current, now()));
  }, []);

  return { ...view, giveCue, logEvent };
}

function tick(s, t, rewardRef) {
  s.confidence = Math.round(rand(0.88, 0.97) * 100) / 100;
  const c = s.command;
  if (c) {
    if (t >= c.obeyAt && s.pose !== c.cue.pose) s.pose = c.cue.pose;
    if (s.pose === c.cue.pose) {
      c.holdStart ??= t;
      if (t - c.holdStart >= c.cue.holdS) {
        const reaction = (c.holdStart - c.startedAt).toFixed(1);
        playClick();                                     // marker first, treat after
        const treat = rewardRef.current?.() ?? false;
        s.last = { kind: "good", text: `Nice! Reacted in ${reaction} s · ${treat ? "treat given" : "daily treat limit reached"}` };
        s.command = null;
        s.nextChange = t + rand(8, 12);
      }
    } else if (t - c.startedAt >= TIMEOUT_S) {
      s.last = { kind: "bad", text: `No reaction to “${c.cue.label}” in ${TIMEOUT_S} s` };
      s.command = null;
      s.nextChange = t + rand(3, 6);
    }
    return;
  }
  if (t >= s.nextChange) {
    s.pose = POSES[Math.floor(Math.random() * POSES.length)];
    s.nextChange = t + rand(6, 12);
  }
}

function snapshot(s, t) {
  const c = s.command;
  const held = c && c.holdStart != null ? Math.min(t - c.holdStart, c.cue.holdS) : 0;
  return {
    pose: s.pose,
    poseLabel: POSE_LABEL[s.pose],
    confidence: s.confidence,
    activeCue: c ? c.cue : null,
    heldS: held,
    holdS: c ? c.cue.holdS : 0,
    rep: s.rep,
    reps: REPS,
    last: s.last,
  };
}
