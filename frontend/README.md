# PawCoach — aplicația (frontend)

Aplicație mobilă (React + Vite), care se deschide în browser pe telefon sau pe laptop.
La pornire caută serverul (`python -m server`, vezi `docs/api.md`):

- **serverul merge** → câinii, programările, statisticile și sesiunea Live vin de la backend;
- **serverul nu merge** → aplicația rulează singură, cu datele mock („offline demo” jos în Settings).

## Pornire

Ai nevoie de Node.js 18+. Din folderul `frontend`:

```bash
npm install
npm run dev
```

Deschide http://localhost:5173. Vite trimite tot ce începe cu `/api` la serverul de pe portul 8000. Pe telefon, conectat la aceeași rețea Wi-Fi, deschide
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
| Live | `#/live` | cameră, comenzi, clicker, microfon, recompensă — de la server (sau simulată, offline) |
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
  api.js                  apelurile către server (/api/...)
  store.jsx               starea aplicației; caută serverul la pornire, altfel folosește mock-ul
  data/fromApi.js         transformă datele serverului în forma folosită de ecrane
  data/mock.js            datele pentru modul offline (și scorul din Leaderboard)
  hooks/useApiLiveSession.js  sesiunea Live de la server (status de 4 ori pe secundă)
  hooks/useLiveSession.js     sesiunea Live simulată în browser (modul offline)
  components/             Icon, BottomNav, CameraView, ui (Avatar, Toggle, Stepper, ...)
  screens/                câte un fișier per ecran
  styles.css              tema pastel (variabilele de culoare sunt sus, în :root)
```

## Legătura cu backend-ul

| Ce | Endpoint |
|---|---|
| câini, statistici, exerciții, momente prinse azi | `GET /api/dogs` |
| graficul „This week” (toți câinii) | `GET /api/stats/daily` |
| Live: poziția, comanda în curs, recompense, evenimente | `GET /api/status` |
| Live: Sit / Down / Stand / Stay | `POST /api/commands` |
| Live: Treat | `POST /api/treat` |
| Live: câinele antrenat | `POST /api/dogs/{id}/select` |
| Live: imaginea camerei (doar cu cameră reală) | `GET /api/video` |
| „Move to step 2” / „Start learning” | `PATCH /api/dogs/{id}/exercises/{ex}` |
| Schedules: pornit/oprit, max treats | `PATCH /api/schedules/{id}` |
| Feeder: „Dispense a test treat” | `POST /api/feeder/test` |

Rămân mock deocamdată: Leaderboard și scorul „Good Boy Score” (au nevoie de un serviciu online
comun), nivelul rezervorului (feederul nu are senzor) și opțiunile camerei.
