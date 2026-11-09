import { useEffect, useState } from "react";
import CameraView from "../components/CameraView.jsx";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { api } from "../api.js";
import { useApiLiveSession } from "../hooks/useApiLiveSession.js";
import { CUES, playClick } from "../hooks/liveCues.js";
import { useStore } from "../store.jsx";

// Live runs only through the server API: cues go to POST /api/commands, and the server reads
// the camera frames with DogDetector + PostureClassifier and reports back in GET /api/status.
// Nothing is simulated in the browser; without the server, Live says so.
export default function Live() {
  const { source, dogs } = useStore();
  if (source !== "api") return <ServerOffline />;
  if (!dogs.length) return <div className="screen"><h1>Live</h1><p className="muted">Add a dog first.</p></div>;
  return <ApiLive />;
}

function ServerOffline() {
  return (
    <div className="screen">
      <h1>Live</h1>
      <div className="card stack-6">
        <strong>Can't reach the PawCoach server</strong>
        <p className="muted small">
          Live training uses the posture classifier on the server. Start it with <code>start-server.bat</code>
          {" "}(or <code>python -m server</code>), then reload the app.
        </p>
        <button type="button" className="btn btn--peach" onClick={() => window.location.reload()}>Try again</button>
      </div>
    </div>
  );
}

function ApiLive() {
  const { dogs, refresh, showToast } = useStore();
  // Demo lock: default to first dog
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
      dogs={dogs}
      dogIndex={dogIndex}
      onSelectDog={(idx) => setDogIndex(idx)}
      session={session}
      treats={`${session.treatsToday} / ${session.treatLimit}`}
      streamSrc={api.videoUrl()}                       // what the server's classifier is looking at
      offline={!session.online}
      onCue={onCue}
      onTreat={session.giveTreat}
    />
  );
}

function LiveView({ dog, dogs = [], dogIndex = 0, onSelectDog, session, treats, streamSrc = null, offline = false, onCue, onTreat }) {
  const [talking, setTalking] = useState(false);
  const [accordionOpen, setAccordionOpen] = useState(false);
  const cue = session.activeCue;
  const progress = cue && cue.holdS ? (session.heldS / cue.holdS) * 100 : 0;

  // Log events to browser console instead of showing bottom banner in UI
  useEffect(() => {
    if (session.last) {
      const { kind, text } = session.last;
      const tag = `[PawCoach Live ${kind?.toUpperCase() || "EVENT"}]`;
      if (kind === "good") {
        console.log(`%c${tag} ${text}`, "color: #3F6B48; font-weight: bold; background: #E5F0E2; padding: 2px 6px; border-radius: 4px;");
      } else if (kind === "bad") {
        console.warn(`%c${tag} ${text}`, "color: #A8432F; font-weight: bold; background: #FCE3D4; padding: 2px 6px; border-radius: 4px;");
      } else {
        console.info(`%c${tag} ${text}`, "color: #2F4E70; font-weight: bold; background: #E3EDF7; padding: 2px 6px; border-radius: 4px;");
      }
    }
  }, [session.last]);

  const onClicker = () => {
    playClick();
    session.logEvent("info", "Click!");
  };

  return (
    <div className="screen screen--live">
      <header className="row-between" style={{ position: "relative", zIndex: 30 }}>
        {/* Accordion Dog Switcher Trigger */}
        <button
          type="button"
          className="dog-switch"
          aria-expanded={accordionOpen}
          aria-label="Toggle pet selector accordion"
          onClick={() => setAccordionOpen((prev) => !prev)}
        >
          <Avatar dog={dog} size={40} />
          <strong>{dog.name}</strong>
          <Icon
            name="chevronDown"
            size={16}
            strokeWidth={2.2}
            style={{
              transform: accordionOpen ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
            }}
          />
        </button>
        <span className="pill">{treats} treats</span>

        {/* CONDITIONAL RENDERING: Accordion dropdown panel. Only the first dog is interactive; others hidden/non-interactable with 'To be continued' */}
        {accordionOpen && (
          <div
            className="dog-accordion-menu card stack-6"
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              left: 0,
              minWidth: 260,
              boxShadow: "0 12px 30px rgba(59, 47, 40, 0.18)",
              border: "1.5px solid var(--line)",
              zIndex: 40,
              padding: 8,
            }}
          >
            <div className="muted tiny" style={{ padding: "4px 8px", fontWeight: 800 }}>
              SELECT ACTIVE PET
            </div>
            {dogs.map((d, idx) => {
              const isFirstDog = idx === 0;
              const isSelected = dogIndex === idx;

              /* CONDITIONAL RENDERING: First dog is interactable */
              if (isFirstDog) {
                return (
                  <button
                    key={d.id}
                    type="button"
                    className="inline-card"
                    style={{
                      border: "0",
                      width: "100%",
                      background: isSelected ? "var(--honey-soft)" : "transparent",
                      borderRadius: 12,
                      padding: "8px 10px",
                      cursor: "pointer",
                    }}
                    onClick={() => {
                      onSelectDog(idx);
                      setAccordionOpen(false);
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Avatar dog={d} size={34} />
                      <div className="left stack-0">
                        <strong style={{ fontSize: 15 }}>{d.name}</strong>
                        <span className="muted tiny">{d.breed}</span>
                      </div>
                    </div>
                    {isSelected && <Icon name="check" size={18} strokeWidth={2.4} className="good" />}
                  </button>
                );
              }

              /* CONDITIONAL RENDERING: Other dogs than the first are non-interactable and marked 'To be continued' */
              return (
                <div
                  key={d.id}
                  className="inline-card is-disabled"
                  aria-disabled="true"
                  style={{
                    opacity: 0.55,
                    cursor: "not-allowed",
                    borderRadius: 12,
                    padding: "8px 10px",
                    background: "transparent",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Avatar dog={d} size={34} />
                    <div className="left stack-0">
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <strong style={{ fontSize: 15 }}>{d.name}</strong>
                        <span className="pill" style={{ fontSize: 10, padding: "1px 6px", background: "var(--soft)" }}>
                          To be continued
                        </span>
                      </div>
                      <span className="muted tiny">{d.breed}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </header>

      <CameraView pose={session.pose} poseLabel={session.poseLabel} streamSrc={streamSrc}>
        {offline && <span className="cam-chip cam-chip--talk">Reconnecting to the feeder…</span>}
        {!offline && talking && <span className="cam-chip cam-chip--talk">Speaking through the speaker…</span>}
      </CameraView>

      <div className="hold-card">
        <div className="small">
          <span>
            {cue ? <>Hold “{cue.label}” · <strong>{session.heldS.toFixed(1)} / {cue.holdS.toFixed(1)} s</strong></>
              : "Pick a cue to start"}
          </span>
        </div>
        <div className="cam-progress"><div style={{ width: `${progress}%` }} /></div>
      </div>

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
    </div>
  );
}
