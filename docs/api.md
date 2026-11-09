# Serverul API (FastAPI)

Serverul din `server/` pornește motorul (`src/app_runtime.py`: camera sau câinele simulat →
poziție → comenzi → recompense) și îl expune aplicației prin HTTP.

## Pornire

O singură dată, din folderul proiectului:

```bash
pip install -r requirements-server.txt
```

Apoi, în două terminale:

```bash
python -m server                 # serverul, pe portul 8000 (câine simulat + câinii demo)
cd frontend && npm run dev       # aplicația, pe portul 5173 (sau dublu-click pe frontend/start.bat)
```

Deschide http://localhost:5173. Documentația interactivă a API-ului: http://localhost:8000/docs

| Opțiune | Ce face |
|---|---|
| `--fresh` | bază de date nouă la fiecare pornire (bun pentru demo) |
| `--mode camera` | camera reală + modelele (YOLO-pose + clasificatorul de poziții) |
| `--camera 1` / `--camera rtsp://...` / `--camera video.mp4` | ce cameră folosește |
| `--feeder COM3` | feederul ESP32 pe USB (fără opțiunea asta, recompensele sunt simulate) |
| `--no-demo` | fără Bruno, Luna și Toby |
| `--port 8000` | alt port |

Datele se păstrează în `data/app/server/` (ignorat de git). Șterge folderul ca să o iei de la capăt.

**Pe telefon:** pornește ambele pe laptop și deschide `http://<IP-ul laptopului>:5173`.
Vite trimite apelurile `/api` mai departe la server, deci nu trebuie configurat nimic.
Dacă rulezi `npm run build`, serverul servește și aplicația direct, la `http://<IP>:8000`.

## Endpoint-uri

Toate sunt sub `/api` și primesc/întorc JSON.

| Metodă | Rută | Ce face |
|---|---|---|
| GET | `/health` | modul (mock / camera) și tipul de feeder |
| GET | `/status` | live: poziția, comanda în curs, sesiunea, recompense azi, ultimele evenimente |
| POST | `/commands` `{exercise}` | `sit` · `down` · `stand` · `stay` — 409 dacă rulează deja una |
| POST | `/commands/cancel` | oprește comanda și sesiunea în curs |
| POST | `/treat` | recompensă manuală (respectă toate limitele) |
| POST | `/feeder/test` | recompensă de test, nu se numără la niciun câine |
| POST | `/sim/pose` `{pose}` | doar în modul mock: forțează poziția câinelui simulat (`auto` = liber) |
| GET | `/video` | imaginea camerei (MJPEG, pentru `<img src>`) |
| GET | `/snapshot.jpg` | un singur cadru |
| GET | `/exercises` | lista exercițiilor |
| GET · POST | `/dogs` | câinii (cu statistici, exerciții, momente prinse azi) / câine nou |
| GET · PATCH · DELETE | `/dogs/{id}` | un câine / modificare / arhivare |
| POST | `/dogs/{id}/select` | câinele antrenat în Live |
| PATCH | `/dogs/{id}/exercises/{ex}` `{stage}` | `next` · `learn` · `train` · `mastered` |
| GET · POST | `/schedules` | programările (`?dog_id=`) / programare nouă |
| PATCH · DELETE | `/schedules/{id}` | modificare (enabled, max_treats, ore...) / ștergere |
| GET | `/highlights` | momentele salvate (`?dog_id=`) |
| GET | `/highlights/{id}/clip` | clipul MP4 |
| GET · PATCH | `/settings` | setările dispozitivului (limita zilnică, timeout, volum...) |
| GET | `/events` | ultimele evenimente (`?dog_id=&limit=`) |
| GET | `/stats/daily` | o linie pe zi (`?dog_id=&days=7`) |

Corpurile cererilor sunt validate (`server/schemas.py`): câmpurile necunoscute sau greșite dau 422.

## Reguli de recompensă

Fiecare recompensă trece prin toate limitele, în ordine: limita zilnică a dispozitivului, pauza
minimă între recompense, limita zilnică a câinelui, apoi limitele programării.

Limitele unei **programări de învățare** (max recompense, una la 30 de minute) se aplică doar
momentelor prinse singur de cameră. Comenzile date din aplicație și butonul Treat nu le consumă.
Într-o **sesiune de antrenament** programată, limita sesiunii se aplică tuturor recompenselor.

## Teste

```bash
python -m pytest            # include tests/test_api.py (se sare dacă FastAPI nu e instalat)
```
