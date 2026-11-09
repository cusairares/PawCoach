# Funcțiile aplicației în backend

Ce există în aplicație (`frontend/`) există acum și în backend, peste pipeline-ul de vision
și peste `BehaviorController`. Serverul HTTP (FastAPI) e în `server/` și e descris în
[`api.md`](api.md); aplicația se conectează la el.

## Încearcă

```bash
python -m src.app_runtime                     # câine simulat, ~30 s, afișează evenimentele
python -m pytest tests/test_app_backend.py    # 17 teste, fără cameră și fără torch
```

## Ce din aplicație există acum și în backend

| În aplicație | În backend |
|---|---|
| Profilurile câinilor, fiecare cu limita lui de recompense | `src/app_store.py` (tabelul `dogs`) |
| Exercițiile cu 3 pași: *Learns on his own → Trains on cue → Mastered* | `src/training_plan.py`, progres salvat per câine |
| „18 of 30 moments caught” | capturile pasive cresc `moments`; la 30 exercițiul trece la antrenament |
| Nivelul (pip-urile) și timpul de menținere care crește | 3 reușite la rând = nivel nou, 2 ratări = un nivel mai jos |
| Comanda **Stay** | `TrainingCommand` cu `hold_s` (pornește de la 3 s, crește până la 15 s) |
| Programări *Learning*: fereastră orară, **max treats**, „una la 30 min” | `src/scheduler.py`; captura pasivă merge doar în fereastră |
| Programări *Training*: sesiuni la ore fixe, 10 repetări, **max treats** pe sesiune | sesiuni automate, oprite la limita de recompense |
| Butonul **Treat** din Live | `BehaviorController.give_treat()` (respectă toate limitele) |
| **Highlights / momente de aur** | `src/highlights.py`: clip MP4 la record personal, prima reușită, nivel nou, exercițiu învățat sau stăpânit |
| Graficul săptămânii, reușita pe 7 zile, seria de zile | `EventLog.daily()`, `EventLog.streak_days()` |

`src/app_runtime.py` le leagă pe toate de pipeline (cameră → postură → vot → comportament), în
modul `mock` (câine simulat) sau `camera`. Datele se salvează în `data/app/` (ignorat de git).

### Modul mock folosește clasificatorul real

Înainte, câinele simulat „sărea” în poziția cerută după 0.8–2.2 s și trimitea probabilități
inventate (88 %), deci orice comandă reușea fără să ruleze vreun model. Acum (`--mock-source
classifier`, implicit la `python -m server`):

1. câinele simulat decide doar **ce face**: ascultă comanda după 1.5–2.5 s, iar când e liber își
   schimbă singur poziția;
2. `src/demo_footage.py` sare la o bucată din `video demo/video demo.mp4` în care un câine e chiar
   în poziția aceea (segmente etichetate **manual** în `video demo/segments.json`, nu de model);
3. cadrele trec prin `DogDetector` + `PostureClassifier`, apoi prin fereastra de consens,
   pragurile și regula „trebuie să *intre* în poziție după comandă” — exact ca la cameră.

Reușita, timpul de reacție și încrederea vin deci din modele. Segmentele pe care modelul actual
le greșește (clipul 3, câinele pe bancă: culcat/șezând citite ca „standing”) sunt marcate `hard`
și sărite implicit; `--mock-hard` le include, ca stress-test. `--mock-source synthetic` păstrează
varianta veche (fără modele; o folosesc și testele). Dacă video-ul, `onnxruntime` sau modelele
lipsesc, serverul trece singur pe `synthetic` și scrie motivul în `status.sim.note`.

Aplicația, când nu găsește serverul, face același lucru în browser: redă video-ul demo pe
segmentul ales și decide din ieșirea clasificatorului precalculată în
`frontend/public/demo/timeline.json`. După ce schimbi modelele, video-ul sau segmentele, rulează
`python tools/demo_timeline.py` (regenerează fișierul și afișează acuratețea pe fiecare segment).

## Ce s-a schimbat în codul existent

- `src/event_log.py`: evenimentele au `dog_id` și `schedule_id` (bazele de date vechi se actualizează
  singure) și există statistici pe zile și pe câine.
- `src/behavior.py`: timp de menținere pe comandă (Stay), limite suplimentare de recompense
  (`treat_guard`), recompensă manuală (`give_treat`) și contextul câinelui sau al programării.
  Logica existentă e neschimbată.

`config.py`, `detector.py` și `posture.py` nu sunt atinse, pentru că se lucrează la ele pe
`feature/skeleton-classifier`. Branch-urile se unesc fără conflicte.
