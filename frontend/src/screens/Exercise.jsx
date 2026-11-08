import Icon from "../components/Icon.jsx";
import { BackLink, Pips, Progress } from "../components/ui.jsx";
import { Link } from "../router.jsx";
import { useStore } from "../store.jsx";
import NotFound from "./NotFound.jsx";

const STEP_INDEX = { learn: 1, train: 2, mastered: 3, next: 0 };

export default function Exercise({ dogId, exerciseId }) {
  const { getDog, setExerciseStage, showToast } = useStore();
  const dog = getDog(dogId);
  const ex = dog?.exercises.find((e) => e.id === exerciseId);
  if (!dog || !ex) return <NotFound />;

  const step = STEP_INDEX[ex.stage];
  const his = dog.pronoun === "she" ? "her" : "his";
  const subtitle = step === 0 ? "Not started yet" : `Step ${step} of 3${ex.startedAgo ? ` · started ${ex.startedAgo}` : ""}`;

  return (
    <div className="screen">
      <BackLink to={`/dogs/${dog.id}`} label={dog.name} />
      <header className="stack-2">
        <h1>{ex.name}</h1>
        <span className="muted">{subtitle}</span>
      </header>

      <ol className="steps">
        <li className={`card step ${step === 1 ? "card--sky is-current" : ""}`}>
          <div className="step-head">
            <span className="step-num step-num--sky">1</span>
            <strong>Learns on {his} own</strong>
          </div>
          <p>
            The camera watches {dog.name}. Every time {dog.pronoun} does it by {dog.pronoun === "she" ? "herself" : "himself"},
            {" "}{dog.pronoun} hears “{ex.name}!” and the clicker, then gets a treat. That's how {dog.pronoun} links
            the word to the move, even when you're not home.
          </p>
          {step === 1 && (
            <>
              <div className="stack-6">
                <div className="row-between small strong sky-ink"><span>Moments caught</span><span>{ex.moments} of {ex.goal}</span></div>
                <Progress value={(ex.moments / ex.goal) * 100} tone="sky" thick />
              </div>
              <Link to="/settings/schedules" className="inline-card">
                <span className="stack-0">
                  <strong>{ex.schedule}</strong>
                  <span className="muted small">{ex.limitNote}</span>
                </span>
                <span className="strong">Change</span>
              </Link>
            </>
          )}
        </li>

        <li className={`card step ${step === 2 ? "card--honey is-current" : ""}`}>
          <div className="step-head">
            <span className="step-num step-num--honey">2</span>
            <strong>Trains on cue</strong>
          </div>
          <p>The app says “{ex.name}!” and {dog.pronoun} has 8 seconds to do it and hold it. The hold time grows as {dog.pronoun} gets it right.</p>
          {step === 2 && (
            <div className="stack-6">
              <div className="row-between small strong"><span>{ex.detail}</span><span className="good">{ex.rate}%</span></div>
              <Pips level={ex.level} />
            </div>
          )}
        </li>

        <li className={`card step ${step === 3 ? "card--sage is-current" : ""}`}>
          <div className="step-head">
            <span className="step-num step-num--sage">3</span>
            <strong>Mastered</strong>
          </div>
          <p>Over 90% success at the top level, 3 days in a row. After that, a quick refresher now and then so {dog.pronoun} doesn't forget.</p>
        </li>
      </ol>

      {step === 1 && ex.caught?.length > 0 && (
        <section className="card card--list" aria-labelledby="caught-h">
          <h2 id="caught-h" className="list-title">Caught today</h2>
          {ex.caught.map(([time, text]) => (
            <div key={time} className="caught-row">
              <time>{time}</time>
              <span className="grow">{text}</span>
              <Icon name="check" size={18} strokeWidth={2.4} className="good" />
            </div>
          ))}
        </section>
      )}

      <div className="btn-row">
        <button type="button" className="btn btn--soft" onClick={() => showToast(`${ex.name} paused for ${dog.name}`)}>Pause</button>
        {step === 1 && (
          <button type="button" className="btn btn--honey grow-2"
            onClick={() => { setExerciseStage(dog.id, ex.id, "train"); showToast(`${dog.name} now trains “${ex.name}” on cue`); }}>
            Move to step 2
          </button>
        )}
        {step >= 2 && <Link to="/live" className="btn btn--honey grow-2">Practice in Live</Link>}
        {step === 0 && (
          <button type="button" className="btn btn--honey grow-2"
            onClick={() => { setExerciseStage(dog.id, ex.id, "learn"); showToast(`${dog.name} started learning “${ex.name}”`); }}>
            Start learning
          </button>
        )}
      </div>
    </div>
  );
}
