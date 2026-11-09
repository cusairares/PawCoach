// Live training session when the app can't reach the server (offline demo).
//
// The simulated dog only decides WHAT it does: after a cue it moves into the pose after a
// moment, when idle it wanders between poses. What "the camera sees" is the demo video: the
// player jumps to a hand-labelled stretch where a dog is in that pose, and the decision comes
// from the real classifier's output for those frames (frontend/public/demo/timeline.json,
// made by tools/demo_timeline.py). Those probabilities go through the same steps as the
// backend (src/consensus.py, src/behavior.py):
//   1 s consensus window -> confirmed pose with hysteresis (enter 0.6 / exit 0.4)
//   -> the dog must *transition into* the cued pose after the cue -> hold it -> success,
//   or time out after TIMEOUT_S.
// So a pose the classifier reads with low confidence really fails, like on the device.
// Without timeline.json it falls back to made-up probabilities (88 % for the dog's pose),
// still through the same consensus steps.
import { useCallback, useEffect, useRef, useState } from "react";

export const CUES = {
  sit: { id: "sit", label: "Sit", pose: "sitting", holdS: 1.0 },
  down: { id: "down", label: "Down", pose: "lying", holdS: 1.0 },
  stand: { id: "stand", label: "Stand", pose: "standing", holdS: 1.0 },
  stay: { id: "stay", label: "Stay", pose: "sitting", holdS: 1.0 },
};

export const POSE_LABEL = { sitting: "Sitting", standing: "Standing", lying: "Lying down" };
export const DEMO_VIDEO_SRC = "/moments/video_demo_annotated.mp4";
const TIMELINE_URL = "/demo/timeline.json";
const POSES = ["sitting", "standing", "lying"];
const LABELS = ["lying", "sitting", "standing", "undefined", "no_dog"];   // backend order + no dog
const TICK_MS = 150;
const TIMEOUT_S = 8;
const REPS = 10;
const OBEY_DELAY_S = [1.5, 2.5];       // long enough for the 1 s window to really leave the old pose
const DEFAULT_CONSENSUS = { window_s: 1.0, min_fill: 0.7, min_entries: 5, enter: 0.6, exit: 0.4 };

const rand = (a, b) => a + Math.random() * (b - a);
const pick = (xs) => xs[Math.floor(Math.random() * xs.length)];
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

function initialState(t) {
  return {
    timeline: null,                                   // classifier output, once loaded
    consensus: DEFAULT_CONSENSUS,
    dog: { pose: "standing", nextChange: t + rand(6, 10), pending: null },
    clip: null,                                       // { pose, start, end, t0 } in video seconds
    clipT: 0,
    frame: null,                                      // { label, confidence } of the current frame
    buf: [],                                          // [{ t, v }] consensus window
    tracker: { state: null, since: 0, entryId: 0 },
    command: null,
    rep: 4,
    last: null,
  };
}

/**
 * @param {object} opts
 * @param {() => boolean} opts.onReward  called on success; returns true if a treat was dispensed
 * @param {{current: HTMLVideoElement|null}} [opts.videoRef]  the demo video, kept on the clip being read
 */
export function useLiveSession({ onReward, videoRef }) {
  const sim = useRef(null);
  sim.current ??= initialState(now());
  const [view, setView] = useState(() => snapshot(sim.current, now()));
  const rewardRef = useRef(onReward);
  rewardRef.current = onReward;
  const videoRefRef = useRef(videoRef);
  videoRefRef.current = videoRef;

  useEffect(() => {
    let cancelled = false;
    fetch(TIMELINE_URL)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((tl) => {
        if (cancelled || !Array.isArray(tl?.probs) || !tl.fps) return;
        const s = sim.current;
        s.timeline = tl;
        s.consensus = { ...DEFAULT_CONSENSUS, ...(tl.consensus ?? {}) };
        s.clip = null;                                // re-pick a real clip for the current pose
      })
      .catch(() => { /* no timeline: synthetic probabilities */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      const t = now();
      tick(sim.current, t, rewardRef, videoRefRef.current?.current ?? null);
      setView(snapshot(sim.current, t));
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  const giveCue = useCallback((cueId) => {
    const s = sim.current;
    const cue = CUES[cueId];
    const t = now();
    if (s.command) return false;                      // backend rejects a second command ("busy")
    // the backend needs a *transition into* the pose: if already there, the dog moves first
    if (s.dog.pose === cue.pose) s.dog.pose = cue.pose === "standing" ? "sitting" : "standing";
    s.dog.pending = { target: cue.pose, at: t + rand(...OBEY_DELAY_S) };
    s.command = { cue, startedAt: t, entryAtStart: s.tracker.entryId };
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

// ------------------------------------------------------------------ simulation step
function tick(s, t, rewardRef, video) {
  stepDog(s.dog, t);
  const probs = sense(s, t, video);
  pushVote(s, t, probs);
  stepCommand(s, t, rewardRef);
}

/** What the simulated dog does (mirrors MockDog in src/app_runtime.py). */
function stepDog(dog, t) {
  if (dog.pending) {
    if (t >= dog.pending.at) {
      dog.pose = dog.pending.target;
      dog.pending = null;
      dog.nextChange = t + rand(8, 14);
    }
    return;
  }
  if (t >= dog.nextChange) {
    dog.pose = pick(POSES);
    dog.nextChange = t + rand(6, 12);
  }
}

/** Probabilities for this moment: the classifier's output on the clip being shown. */
function sense(s, t, video) {
  const tl = s.timeline;
  const segs = tl?.segments?.[s.dog.pose];
  if (!tl || !segs?.length) {                           // synthetic fallback
    s.clip = null;
    const v = [0.03, 0.03, 0.03, 0.03];
    v[LABELS.indexOf(s.dog.pose)] = 0.88;
    const sum = v.reduce((a, b) => a + b, 0);
    const probs = v.map((x) => x / sum);
    s.frame = { label: s.dog.pose, confidence: probs[LABELS.indexOf(s.dog.pose)] };
    return probs;
  }
  if (!s.clip || s.clip.pose !== s.dog.pose) {
    const [start, end] = pick(segs);
    s.clip = { pose: s.dog.pose, start, end, t0: t };
  }
  const { start, end, t0 } = s.clip;
  s.clipT = start + ((t - t0) % Math.max(0.1, end - start));
  syncVideo(video, s.clipT);
  const i = Math.min(tl.probs.length - 1, Math.round(s.clipT * tl.fps));
  const probs = tl.probs[i];
  if (!probs) {
    s.frame = null;
    return null;                                        // no dog detected in this frame
  }
  let k = 0;
  for (let j = 1; j < 3; j++) if (probs[j] > probs[k]) k = j;
  s.frame = { label: probs[3] > probs[k] ? "undefined" : LABELS[k], confidence: Math.max(probs[k], probs[3]) };
  return probs;
}

function syncVideo(video, clipT) {
  if (!video || video.readyState < 1) return;
  try {
    if (Math.abs(video.currentTime - clipT) > 0.35) video.currentTime = clipT;
    if (video.paused) video.play().catch(() => {});
  } catch { /* video is only the picture; the decision doesn't depend on it */ }
}

/** ConsensusBuffer.vote + StateTracker.update (src/consensus.py). */
function pushVote(s, t, probs) {
  const c = s.consensus;
  const vec = probs ? [...probs, 0] : [0, 0, 0, 0, 1];
  s.buf.push({ t, v: vec });
  while (s.buf.length && s.buf[0].t < t - c.window_s) s.buf.shift();
  const n = s.buf.length;
  const fill = n > 1 ? Math.min(1, (t - s.buf[0].t) / c.window_s) : 0;
  if (fill < c.min_fill || n < c.min_entries) return;   // vote not ready
  const mean = LABELS.map((_, j) => s.buf.reduce((a, e) => a + e.v[j], 0) / n);
  let k = 0;
  for (let j = 1; j < mean.length; j++) if (mean[j] > mean[k]) k = j;
  const tr = s.tracker;
  if (tr.state !== null && mean[LABELS.indexOf(tr.state)] < c.exit) {
    tr.state = null;
    tr.since = t;
  }
  if (LABELS[k] !== tr.state && mean[k] >= c.enter) {
    tr.state = LABELS[k];
    tr.since = t;
    tr.entryId += 1;
  }
}

/** BehaviorController._update_command (src/behavior.py). */
function stepCommand(s, t, rewardRef) {
  const c = s.command;
  if (!c) return;
  const tr = s.tracker;
  const entered = tr.entryId > c.entryAtStart;
  if (tr.state === c.cue.pose && entered && t - tr.since >= c.cue.holdS) {
    const reaction = (tr.since - c.startedAt).toFixed(1);
    playClick();                                        // marker first, treat after
    const treat = rewardRef.current?.() ?? false;
    s.last = { kind: "good", text: `Nice! Reacted in ${reaction} s · ${treat ? "treat given" : "daily treat limit reached"}` };
    s.command = null;
  } else if (t - c.startedAt >= TIMEOUT_S) {
    const seen = s.frame ? `${s.frame.label} ${Math.round(s.frame.confidence * 100)}%` : "no dog";
    s.last = { kind: "bad", text: `No reaction to “${c.cue.label}” in ${TIMEOUT_S} s (classifier saw: ${seen})` };
    s.command = null;
  }
}

function snapshot(s, t) {
  const c = s.command;
  const tr = s.tracker;
  const pose = tr.state && POSE_LABEL[tr.state] ? tr.state : null;
  const holding = c && tr.state === c.cue.pose && tr.entryId > c.entryAtStart;
  return {
    source: s.timeline ? "classifier" : "synthetic",
    pose,
    poseLabel: pose ? POSE_LABEL[pose] : tr.state === "undefined" ? "Unsure" : null,
    confidence: s.frame ? Math.round(s.frame.confidence * 100) / 100 : 0,
    activeCue: c ? c.cue : null,
    heldS: holding ? Math.min(t - tr.since, c.cue.holdS) : 0,
    holdS: c ? c.cue.holdS : 0,
    rep: s.rep,
    reps: REPS,
    last: s.last,
    clipT: s.clip ? s.clipT : null,
  };
}
