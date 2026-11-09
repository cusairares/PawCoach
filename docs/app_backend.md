# Funcțiile aplicației în backend

Ce există în aplicație (`frontend/`) există acum și în backend, peste pipeline-ul de vision
și peste `BehaviorController`. **Nu există încă un server HTTP.** Aplicația merge în continuare pe
date de test. API-ul se va face separat, cu FastAPI, folosind `src/app_runtime.py`.

## Încearcă

```bash
python -m src.app_runtime                     # câine simulat, ~30 s, afișează evenimentele
python -m pytest tests/test_app_backend.py    # 16 teste, fără cameră și fără torch
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

## Ce s-a schimbat în codul existent

- `src/event_log.py`: evenimentele au `dog_id` și `schedule_id` (bazele de date vechi se actualizează
  singure) și există statistici pe zile și pe câine.
- `src/behavior.py`: timp de menținere pe comandă (Stay), limite suplimentare de recompense
  (`treat_guard`), recompensă manuală (`give_treat`) și contextul câinelui sau al programării.
  Logica existentă e neschimbată.

`config.py`, `detector.py` și `posture.py` nu sunt atinse, pentru că se lucrează la ele pe
`feature/skeleton-classifier`. Branch-urile se unesc fără conflicte.
