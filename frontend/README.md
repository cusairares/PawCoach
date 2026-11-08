# PawCoach — aplicația (frontend)

Prototip de aplicație mobilă (React + Vite), care se deschide în browser pe telefon sau pe laptop.
**Rulează singură, cu date mock**: nu are nevoie de backend.

## Pornire

Ai nevoie de Node.js 18+. Din folderul `frontend`:

```bash
npm install
npm run dev
```

Deschide http://localhost:5173. Pe telefon, conectat la aceeași rețea Wi-Fi, deschide
`http://<IP-ul laptopului>:5173`. Adresa apare în terminal la „Network”.

Pentru o versiune finală: `npm run build` (rezultatul e în `frontend/dist/`).

## Ecrane

Meniul de jos: **Home · Moments · Live · Leaderboard · Settings**

| Ecran | Ruta | Ce face |
|---|---|---|
| Home | `#/home` | câinii, graficul săptămânii (filtru pe câine) |
| Dog | `#/dogs/bruno` | profilul unui câine: ce învață, ce antrenează, ce urmează |
| Exercise | `#/dogs/bruno/exercises/down` | cei 3 pași: Learns on his own → Trains on cue → Mastered |
| Moments | `#/moments` | gol deocamdată (doar butonul din meniu) |
| Live | `#/live` | cameră, comenzi, clicker, microfon, recompensă — **sesiune simulată** |
| Leaderboard | `#/leaderboard` | „Who's the goodest boy?”, pe zone și categorii |
| Settings | `#/settings` | listă de setări |
| Schedules | `#/settings/schedules` | programări cu limită de recompense, totaluri pe zi |
| Feeder | `#/settings/feeder` | rezervor, porție, recompensă de test |
| Camera | `#/settings/camera` | zona de antrenament, opțiuni |

## Structura

```
src/
  App.jsx                 rutele + meniul de jos
  router.jsx              router pe hash (#/...), fără dependențe
  store.jsx               starea aplicației (câini, programări, feeder, cameră, notificări)
  data/mock.js            toate datele mock
  hooks/useLiveSession.js simularea sesiunii live (imită src/behavior.py din backend)
  components/             Icon, BottomNav, CameraView, ui (Avatar, Toggle, Stepper, ...)
  screens/                câte un fișier per ecran
  styles.css              tema pastel (variabilele de culoare sunt sus, în :root)
```

## Legătura cu backend-ul

Backend-ul nu a fost modificat. Ce îi trebuie aplicației de la el e în
[`BACKEND_QUESTIONS.md`](BACKEND_QUESTIONS.md). Locurile de înlocuit când va exista un API:

- `hooks/useLiveSession.js` → statusul live și comenzile (Q1–Q4, Q6);
- `components/CameraView.jsx` → imaginea reală de la cameră (Q5);
- `store.jsx` și `data/mock.js` → câini, statistici, programări, setări (Q8–Q17).
