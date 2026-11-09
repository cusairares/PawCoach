import { useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { DOG_PHOTO_PRESETS, WEEK_ALL, WEEK_DAYS } from "../data/mock.js";
import { Link } from "../router.jsx";
import { useStore } from "../store.jsx";

function today() {
  return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

function AddDogModal({ open, onClose }) {
  const { addDog } = useStore();
  const fileInputRef = useRef(null);
  const [name, setName] = useState("");
  const [breed, setBreed] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [image, setImage] = useState(DOG_PHOTO_PRESETS[0]);

  if (!open) return null;

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (ev.target?.result) setImage(ev.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    addDog({
      name,
      breed: breed || "Mixed breed",
      age: age || "1 yr",
      weight: weight || "15 kg",
      image,
    });
    setName("");
    setBreed("");
    setAge("");
    setWeight("");
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Add a pet">
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add a pet</h2>
          <button type="button" className="icon-btn icon-btn--sm" onClick={onClose} aria-label="Close">
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="stack-14">
          <div className="form-image-picker">
            <div className="avatar-preview-wrap">
              <Avatar dog={{ name: name || "Pet", image }} size={80} />
            </div>
            <div className="stack-6 grow">
              <button
                type="button"
                className="btn btn--soft btn--sm"
                onClick={() => fileInputRef.current?.click()}
              >
                Upload custom photo
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                style={{ display: "none" }}
              />
              <span className="muted tiny">Or pick a photo:</span>
              <div className="preset-row">
                {DOG_PHOTO_PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={`preset-btn ${image === p ? "is-selected" : ""}`}
                    onClick={() => setImage(p)}
                  >
                    <img src={p} alt={`Preset ${idx + 1}`} />
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="pet-name">Pet name *</label>
            <input
              id="pet-name"
              required
              className="text-input"
              placeholder="e.g. Max"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form-row-2">
            <div className="form-field">
              <label htmlFor="pet-age">Age</label>
              <input
                id="pet-age"
                className="text-input"
                placeholder="e.g. 2 yrs"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
            <div className="form-field">
              <label htmlFor="pet-weight">Weight</label>
              <input
                id="pet-weight"
                className="text-input"
                placeholder="e.g. 18 kg"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
              />
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="pet-breed">Breed</label>
            <input
              id="pet-breed"
              className="text-input"
              placeholder="e.g. Golden Retriever"
              value={breed}
              onChange={(e) => setBreed(e.target.value)}
            />
          </div>

          <div className="btn-row" style={{ marginTop: 8 }}>
            <button type="button" className="btn btn--soft" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--honey grow-2">
              Save pet
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Home() {
  const { dogs } = useStore();
  const [filter, setFilter] = useState("all");
  const [showAddModal, setShowAddModal] = useState(false);

  const selectedDog = dogs.find((d) => d.id === filter);
  const week = filter === "all" ? WEEK_ALL : (selectedDog?.week || WEEK_ALL);
  const avg = Math.round(week[week.length - 1]);

  return (
    <div className="screen">
      <header className="screen-header">
        <div>
          <span className="eyebrow-muted">{today()}</span>
          <h1>My dogs</h1>
        </div>
        <button
          type="button"
          className="icon-btn"
          aria-label="Add a dog"
          onClick={() => setShowAddModal(true)}
        >
          <Icon name="plus" size={20} strokeWidth={2.2} />
        </button>
      </header>

      <section className="stack-12" aria-label="My dogs">
        {dogs.map((d) => (
          <Link key={d.id} to={`/dogs/${d.id}`} className="card dog-row">
            <Avatar dog={d} size={56} />
            <span className="dog-row-text">
              <strong>{d.name}</strong>
              <span className="muted">{d.breed} · {d.age}</span>
              <span className="good small">{d.successesToday} successes today · {d.treatsToday} treats</span>
            </span>
            <Icon name="chevronRight" size={20} className="muted" />
          </Link>
        ))}
      </section>

      <section className="card stack-14" aria-labelledby="week-h">
        <div className="row-between">
          <h2 id="week-h">This week</h2>
          <span className="good strong">{avg}% success</span>
        </div>
        <div className="chips" role="group" aria-label="Filter by dog">
          {[["all", "All"], ...dogs.map((d) => [d.id, d.name])].map(([id, label]) => (
            <button key={id} type="button" className="chip-btn" aria-pressed={filter === id} onClick={() => setFilter(id)}>
              {label}
            </button>
          ))}
        </div>
        <div className="bars" role="img" aria-label={`Success rate this week, ending at ${avg}% today`}>
          {week.map((v, i) => (
            <div key={i} className="bar-col">
              <span className="bar-value">{v}%</span>
              <div className={`bar ${i === week.length - 1 ? "is-today" : ""}`} style={{ height: `${v * 1.2}px` }} />
              <span className={`bar-label ${i === week.length - 1 ? "is-today" : ""}`}>{WEEK_DAYS[i]}</span>
            </div>
          ))}
        </div>
      </section>

      <AddDogModal open={showAddModal} onClose={() => setShowAddModal(false)} />
    </div>
  );
}
