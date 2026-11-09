// Cues, pose names and the phone-side sounds for the Live screen.
// The session itself runs on the server (useApiLiveSession.js -> /api/commands, /api/status),
// where the camera frames go through DogDetector + PostureClassifier.

export const CUES = {
  sit: { id: "sit", label: "Sit", pose: "sitting", holdS: 1.0 },
  down: { id: "down", label: "Down", pose: "lying", holdS: 1.0 },
  stand: { id: "stand", label: "Stand", pose: "standing", holdS: 1.0 },
  stay: { id: "stay", label: "Stay", pose: "sitting", holdS: 1.0 },
};

export const POSE_LABEL = { sitting: "Sitting", standing: "Standing", lying: "Lying down" };

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
