import { Avatar, BackLink, Pips, Progress } from "../components/ui.jsx";
import { Link } from "../router.jsx";
import { useStore } from "../store.jsx";
import NotFound from "./NotFound.jsx";

export default function Dog({ dogId }) {
  const { getDog, showToast } = useStore();
  const dog = getDog(dogId);
  if (!dog) return <NotFound />;

  const learning = dog.exercises.filter((e) => e.stage === "learn");
  const training = dog.exercises.filter((e) => e.stage === "train");
  const mastered = dog.exercises.filter((e) => e.stage === "mastered");
  const next = dog.exercises.filter((e) => e.stage === "next");

  return (
    <div className="screen">
      <BackLink to="/home" label="Home" />

      <header className="dog-hero">
        <Avatar dog={dog} size={96} />
        <div className="stack-2 center">
          <h1>{dog.name}</h1>
          <span className="muted">{[dog.breed, dog.age, dog.weight].filter(Boolean).join(" · ")}</span>
        </div>
        <div className="chips chips--center">
          {dog.score != null && <span className="pill pill--honey">Good Boy Score {dog.score}</span>}
          {dog.rank != null && <span className="pill">#{dog.rank} in {dog.city}</span>}
          <span className="pill">{dog.streak}-day streak</span>
        </div>
      </header>

      <div className="kpis">
        <div className="kpi"><strong>{dog.success7d}%</strong><span>success · 7 days</span></div>
        <div className="kpi"><strong>{dog.reaction}</strong><span>avg reaction</span></div>
        <div className="kpi"><strong>{dog.treatsToday}</strong><span>treats today</span></div>
      </div>

      {learning.length > 0 && (
        <section className="stack-10" aria-labelledby="learn-h">
          <h2 id="learn-h">Learning now</h2>
          {learning.map((e) => (
            <Link key={e.id} to={`/dogs/${dog.id}/exercises/${e.id}`} className="card card--sky stack-10">
              <div className="row-between">
                <strong className="ex-name">{e.name}</strong>
                <span className="sky-ink small strong">{e.moments} of {e.goal} moments</span>
              </div>
              <Progress value={(e.moments / e.goal) * 100} tone="sky" />
              <span className="sky-ink small">
                When {dog.pronoun} does it on {dog.pronoun === "she" ? "her" : "his"} own, {dog.pronoun} hears “{e.name}!” and gets a treat.
              </span>
            </Link>
          ))}
        </section>
      )}

      {training.length > 0 && (
        <section className="stack-10" aria-labelledby="train-h">
          <h2 id="train-h">Training on cue</h2>
          {training.map((e) => (
            <Link key={e.id} to={`/dogs/${dog.id}/exercises/${e.id}`} className="card stack-10">
              <div className="row-between">
                <strong className="ex-name">{e.name}</strong>
                <span className="good strong">{e.rate}%</span>
              </div>
              <Pips level={e.level} />
              <span className="muted small">{e.detail}</span>
            </Link>
          ))}
        </section>
      )}

      {mastered.length > 0 && (
        <section className="stack-10" aria-labelledby="mastered-h">
          <h2 id="mastered-h">Mastered</h2>
          {mastered.map((e) => (
            <Link key={e.id} to={`/dogs/${dog.id}/exercises/${e.id}`} className="card card--sage row-between">
              <strong className="ex-name">{e.name}</strong>
              <span className="good strong">{e.rate}%</span>
            </Link>
          ))}
        </section>
      )}

      <section className="stack-10" aria-labelledby="next-h">
        <h2 id="next-h">Up next</h2>
        <div className="card card--list">
          {next.map((e) => (
            <div key={e.id} className="next-row stack-0">
              <strong>{e.name}</strong>
              <span className="muted small">{e.detail}</span>
            </div>
          ))}
          <button type="button" className="list-action" onClick={() => showToast("Choosing exercises isn't in the mockup yet")}>
            + Choose what {dog.pronoun} learns next
          </button>
        </div>
      </section>
    </div>
  );
}
