import { useState } from "react";
import CameraView from "../components/CameraView.jsx";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { api } from "../api.js";
import { useApiLiveSession } from "../hooks/useApiLiveSession.js";
import { CUES, playClick, useLiveSession } from "../hooks/useLiveSession.js";
import { useStore } from "../store.jsx";

// Live has two engines with the same view:
//   ApiLive   the backend runs the session (camera or simulated dog on the server)
//   MockLive  no server: the session is simulated in the browser
export default function Live() {
  const { source, dogs } = useStore();
  if (!dogs.length) return <div className="screen"><h1>Live</h1><p className="muted">Add a dog first.</p></div>;
  return source === "api" ? <ApiLive /> : <MockLive />;
}

function ApiLive() {
  const { dogs, refresh, showToast } = useStore();
  const [dogIndex, setDogIndex] = useState(0);
  const dog = dogs[dogIndex % dogs.length];
  const session = useApiLiveSession({ dog, onChange: () => refresh().catch(() => {}) });

  const onCue = async (id) => {
    const r = await session.giveCue(id);
    if (!r.ok) showToast(r.reason === "busy" ? "Wait for the current cue to finish" : r.reason);
  };

  return (
    <LiveView
      dog={dog}
      session={session}
      treats={`${session.treatsToday} / ${session.treatLimit}`}
      streamSrc={session.mode === "camera" ? api.videoUrl() : null}
      offline={!session.online}
      onSwitchDog={() => setDogIndex((i) => (i + 1) % dogs.length)}
      onCue={onCue}
      onTreat={session.giveTreat}
    />
  );
}

function MockLive() {
  const { dogs, giveTreat, addSuccess, showToast } = useStore();
  const [dogIndex, setDogIndex] = useState(0);
  const dog = dogs[dogIndex % dogs.length];

  const session = useLiveSession({
    onReward: () => {
      addSuccess(dog.id);
      return giveTreat(dog.id);
    },
  });

  const onCue = (id) => {
    if (!session.giveCue(id)) showToast("Wait for the current cue to finish");
  };
  const onTreat = () => {
    const ok = giveTreat(dog.id);
    session.logEvent(ok ? "good" : "bad", ok ? "Treat given" : "Daily treat limit reached");
  };

  return (
    <LiveView
      dog={dog}
      session={session}
      treats={`${dog.treatsToday} / ${dog.treatLimit}`}
      onSwitchDog={() => setDogIndex((i) => (i + 1) % dogs.length)}
      onCue={onCue}
      onTreat={onTreat}
    />
  );
}

function LiveView({ dog, session, treats, streamSrc = null, offline = false, onSwitchDog, onCue, onTreat }) {
  const [talking, setTalking] = useState(false);
  const cue = session.activeCue;
  const progress = cue && cue.holdS ? (session.heldS / cue.holdS) * 100 : 0;

  const onClicker = () => {
    playClick();
    session.logEvent("info", "Click!");
  };

  return (
    <div className="screen screen--live">
      <header className="row-between">
        <button type="button" className="dog-switch" aria-label="Switch dog" onClick={onSwitchDog}>
          <Avatar dog={dog} size={40} />
          <strong>{dog.name}</strong>
          <Icon name="chevronDown" size={16} strokeWidth={2.2} />
        </button>
        <span className="pill">{treats} treats</span>
      </header>

      <CameraView pose={session.pose} poseLabel={session.poseLabel} confidence={session.confidence} streamSrc={streamSrc}>
        {offline && <span className="cam-chip cam-chip--talk">Reconnecting to the feeder…</span>}
        {!offline && talking && <span className="cam-chip cam-chip--talk">Speaking through the speaker…</span>}
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
