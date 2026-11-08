import { useState } from "react";
import CameraView from "../components/CameraView.jsx";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { CUES, playClick, useLiveSession } from "../hooks/useLiveSession.js";
import { useStore } from "../store.jsx";

export default function Live() {
  const { dogs, giveTreat, addSuccess, showToast } = useStore();
  const [dogIndex, setDogIndex] = useState(0);
  const [talking, setTalking] = useState(false);
  const dog = dogs[dogIndex];

  const session = useLiveSession({
    onReward: () => {
      addSuccess(dog.id);
      return giveTreat(dog.id);
    },
  });
  const cue = session.activeCue;
  const progress = cue ? (session.heldS / session.holdS) * 100 : 0;

  const onCue = (id) => {
    if (!session.giveCue(id)) showToast("Wait for the current cue to finish");
  };
  const onTreat = () => {
    const ok = giveTreat(dog.id);
    session.logEvent(ok ? "good" : "bad", ok ? "Treat given" : "Daily treat limit reached");
  };
  const onClicker = () => {
    playClick();
    session.logEvent("info", "Click!");
  };

  return (
    <div className="screen screen--live">
      <header className="row-between">
        <button type="button" className="dog-switch" aria-label="Switch dog"
          onClick={() => setDogIndex((i) => (i + 1) % dogs.length)}>
          <Avatar dog={dog} size={40} />
          <strong>{dog.name}</strong>
          <Icon name="chevronDown" size={16} strokeWidth={2.2} />
        </button>
        <span className="pill">{dog.treatsToday} / {dog.treatLimit} treats</span>
      </header>

      <CameraView pose={session.pose} poseLabel={session.poseLabel} confidence={session.confidence}>
        {talking && <span className="cam-chip cam-chip--talk">Speaking through the speaker…</span>}
        <div className="cam-hold">
          <div className="row-between small">
            <span>
              {cue ? <>Hold “{cue.label}” · <strong>{session.heldS.toFixed(1)} / {cue.holdS.toFixed(1)} s</strong></>
                : "Pick a cue to start"}
            </span>
            <span>Rep <strong>{session.rep}/{session.reps}</strong></span>
          </div>
          <div className="cam-progress"><div style={{ width: `${progress}%` }} /></div>
        </div>
      </CameraView>

      <div className="cue-grid" role="group" aria-label="Cues">
        {Object.values(CUES).map((c) => (
          <button key={c.id} type="button" className="cue" aria-pressed={cue?.id === c.id} onClick={() => onCue(c.id)}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="controls">
        <button type="button" className="btn btn--white" onClick={onClicker}>Clicker</button>
        <button type="button" className={`mic ${talking ? "is-on" : ""}`} aria-pressed={talking}
          aria-label="Talk to your dog" onClick={() => setTalking((v) => !v)}>
          <Icon name="mic" size={32} strokeWidth={2} />
        </button>
        <button type="button" className="btn btn--peach" onClick={onTreat}>Treat</button>
      </div>
      <p className="mic-hint">
        {talking ? "Your dog can hear you · tap again to stop" : "Tap and talk: a new cue or just “good boy!”"}
      </p>

      {session.last && (
        <div className={`event event--${session.last.kind}`} role="status">
          {session.last.kind === "good" && <Icon name="check" size={20} strokeWidth={2.2} />}
          <span>{session.last.text}</span>
        </div>
      )}
    </div>
  );
}
