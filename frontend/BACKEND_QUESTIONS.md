# Întrebări pentru backend

Frontend-ul e un **prototip care rulează singur**: toate datele sunt mock (`src/data/mock.js`),
iar sesiunea din Live e simulată în browser (`src/hooks/useLiveSession.js`).
Backend-ul **nu a fost modificat**. Mai jos e tot ce ar trebui să existe sau să fie decis în backend
ca aplicația să funcționeze cu datele reale. Numerele (Q1, Q2…) apar și în comentariile din cod.

## Conexiunea aplicație ↔ dispozitiv

**Q1. Cum vorbește aplicația cu backend-ul?**
În `src/` nu există încă un server HTTP. Docstring-urile din `config.py` pomenesc `PATCH /settings`
și „pushed to the device”, deci e plănuit. Ce framework (FastAPI/Starlette/Flask), ce port, ce prefix (`/api`)?
Am un draft de API gata scris și testat (folder separat `api/`, nu atinge `src/`), pe care îl putem
folosi ca punct de plecare dacă vreți.

**Q2. Ce primește aplicația în timp real pe ecranul Live?**
Propunere: postura confirmată (`StateTracker.state`), încrederea, cât timp e menținută (`held_for`),
`BehaviorController.status()` (mod, comandă activă, `remaining_s`, `treats_today`) și ultimele evenimente.
Prin polling (de ex. la 300 ms) sau WebSocket?

**Q3. Cum trimite aplicația o comandă și ce răspuns primește?**
`BehaviorController.submit()` pune comanda în coadă. Dacă rulează deja una, rezultatul
`command_rejected / busy` apare abia la următorul cadru. Aplicația are nevoie de un răspuns imediat,
de exemplu `409 Busy`. Mai e nevoie și de un endpoint de anulare (`cancel()` există).

**Q4. Comanda „Stay”.**
Aplicația are butonul Stay, dar backend-ul știe doar `sit / down / stand` (`POSE_TO_CUE`).
Stay = „sitting” cu un timp de menținere mai lung? Atunci `CommandRequest` ar trebui să primească și
`dwell_s`, nu doar `pose`.

**Q5. Imaginea live de la cameră.**
MJPEG, WebRTC sau doar snapshot-uri? Chenarul câinelui îl desenează serverul în imagine,
sau trimite coordonatele (`Detection.box`) și îl desenează aplicația?

**Q6. Butoanele „Treat” și „Clicker” din Live.**
Nu există endpoint pentru o recompensă manuală. Trebuie să respecte `daily_treat_limit` și
`min_seconds_between_treats`? Cu ce `kind` se loghează în `EventLog` (de ex. `manual_treat`)?
Clicker-ul ar reda doar sunetul `marker`.

**Q7. Butonul de microfon („Talk to your dog”).**
Vrem vocea live din telefon în difuzorul dispozitivului (streaming), sau doar înregistrarea comenzilor
cu vocea stăpânului (`set_custom_sound` există, dar nu are încă un endpoint de upload)?

**Q18. Cum găsește telefonul dispozitivul?** IP introdus manual, mDNS (`pawcoach.local`) sau un server cloud?

## Date și logică

**Q8. Mai mulți câini.**
Backend-ul e gândit pentru un singur câine: evenimentele nu au `dog_id`, iar setările și limitele sunt globale.
Aplicația are profiluri separate (Bruno, Luna, Toby), fiecare cu limitele și statisticile lui.
Unde stocăm profilurile? Cum știe backend-ul ce câine e în cadru: selectat din aplicație sau recunoscut automat?

**Q9. Etapele unui exercițiu: Learns on his own → Trains on cue → Mastered.**
Backend-ul are `passive_enabled` și `passive_poses` globale. Aplicația ține etapa *per câine, per exercițiu*
și arată progresul („18 of 30 moments caught”). Cine ține etapa? Cine o avansează și după ce praguri
(30 de capturi pasive? 90% reușită 3 zile la rând)?

**Q10. Programările (Settings › Schedules).**
În backend nu există un planificator. Aplicația are ferestre orare (de ex. „Daily, 10:00–17:00”),
o limită de recompense per programare și „cel mult una la 30 de minute”.
Atenție: `passive_pose_cooldown_s` este implicit **30 de secunde**, nu 30 de minute.
Cine pornește și oprește modurile la orele programate?

**Q11. Limitele de recompense.**
`daily_treat_limit` (20) și `min_seconds_between_treats` (10 s) sunt globale.
Aplicația arată limite *per câine* (35 / 24 / 18) și per programare. Cum le împăcăm?

**Q12. Statistici pentru grafice și profil.**
`EventLog.stats(since)` dă totaluri pe postură de la un moment dat. Aplicația mai are nevoie de:
- seria pe zile (graficul săptămânal);
- rata de reușită pe 7 zile și reacția medie;
- seria de zile consecutive (streak);
- **nivelul** fiecărui exercițiu (timpul de menținere care crește: 1,5 s → 2,0 s…).

În backend `active_dwell_s` e fix. Vrem dificultate adaptivă?

**Q13. Clasamentul și Good Boy Score.**
Clasamentul pe cartier, oraș și țară cere un server comun (cloud) și conturi. Intră în hackathon
sau rămâne mock? Cum se calculează scorul?

## Hardware

**Q14. Starea feeder-ului.** `Feeder` are doar `dispense()`. Aplicația arată online/offline,
nivelul rezervorului, mărimea porției, versiunea de firmware și o recompensă de test.
Extindem protocolul serial (acum `D\n` → `OK\n`), de exemplu cu `S\n` → status?

**Q15. Setările camerei.** Zona de antrenament, vederea de noapte, microfonul și difuzorul
nu există în backend. Zona ar trebui folosită la detecție (ignorăm câinii din afara ei)?

**Q16. Moments.** Ecranul e gol deocamdată. Pe viitor: clipuri salvate automat la reușite sau recorduri.
Le salvează backend-ul?

**Q17. Ce setări din `AppSettings` expunem în aplicație?**
`passive_enabled`, `passive_poses`, `passive_pose_cooldown_s`, `passive_sound_when_treat_blocked`,
`active_command_timeout_s`, `active_command_play_cue`, `active_command_reward`, `daily_treat_limit`,
`min_seconds_between_treats`, `volume`. Le punem în Schedules, într-un ecran separat de reguli sau ascunse?
