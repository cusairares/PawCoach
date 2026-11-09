"""FastAPI server for the PawCoach app (frontend/).

Wraps ``src.app_runtime.AppRuntime``: the engine runs on its own thread (camera or simulated
dog -> posture -> behavior -> treats), and these endpoints read its state and send it the
app's actions. Start it with ``python -m server`` (see server/__main__.py for the options).

All endpoints are under /api. Interactive docs: http://localhost:8000/docs
If frontend/dist exists (``npm run build``), the app itself is served at http://localhost:8000/
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src import training_plan as plan
from src.app_runtime import AppRuntime, Busy
from src.app_store import Dog, Schedule
from src.config import ROOT
from src.live_view import encode_jpeg, render_frame

from .schemas import (CommandIn, DogIn, DogPatch, ScheduleIn, SchedulePatch, SettingsPatch, SimPoseIn,
                      StageIn)

log = logging.getLogger("server")

DEFAULT_DATA_DIR = ROOT / "data" / "app" / "server"      # git-ignored (data/app/.gitignore)
FRONTEND_DIST = ROOT / "frontend" / "dist"
VIDEO_FPS = 12


def runtime_from_env() -> AppRuntime:
    """Builds the engine from the environment variables set by ``python -m server``."""
    return AppRuntime(mode=os.getenv("PAWCOACH_MODE", "mock"),
                      camera_source=os.getenv("CAMERA_SOURCE", "0"),
                      data_dir=Path(os.getenv("PAWCOACH_DATA", str(DEFAULT_DATA_DIR))),
                      demo=os.getenv("PAWCOACH_DEMO", "1") == "1")


def _format_validation_error(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p != "body"]
        field = ".".join(loc)
        msg = err.get("msg", "Invalid value")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        parts.append(f"Invalid {field}: {msg}" if field else msg)
    return "; ".join(parts) or "Invalid request body"


def create_app(runtime: Optional[AppRuntime] = None, run_loop: bool = True) -> FastAPI:
    """``run_loop=False`` (tests): the engine thread isn't started, call ``runtime.step()`` yourself."""
    rt = runtime or runtime_from_env()
    store = rt.store

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_loop:
            rt.start()
            log.info("engine started (%s mode)", rt.mode)
        yield
        rt.stop()

    app = FastAPI(title="PawCoach API", version="0.1", lifespan=lifespan)
    app.state.runtime = rt
    # The app runs on another port in development (Vite, :5173) and on phones on the same Wi-Fi.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": _format_validation_error(exc)})

    def get_dog(dog_id: int) -> Dog:
        dog = store.dog(dog_id)
        if dog is None or dog.archived:
            raise HTTPException(404, "Dog not found")
        return dog

    def get_schedule(schedule_id: int) -> Schedule:
        s = store.schedule(schedule_id)
        if s is None:
            raise HTTPException(404, "Schedule not found")
        return s

    # ------------------------------------------------------------------ live
    @app.get("/api/health", tags=["live"])
    def health():
        return {"ok": True, "mode": rt.mode, "feeder": type(rt.feeder).__name__,
                "camera": rt.mode == "camera"}

    @app.get("/api/status", tags=["live"])
    def status():
        """Live state: posture, running command, session, treats today, latest events."""
        return rt.status()

    @app.post("/api/commands", status_code=202, tags=["live"])
    def give_command(body: CommandIn):
        """Plays the cue and waits for the dog. 409 if a command is already running."""
        try:
            return {"command_id": rt.submit_command(body.exercise)}
        except Busy as exc:
            raise HTTPException(409, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/commands/cancel", tags=["live"])
    def cancel_command():
        rt.cancel_command()
        return {"ok": True}

    @app.post("/api/treat", tags=["live"])
    def manual_treat():
        """Treat button in Live. Respects every limit; ``ok: false`` + ``reason`` when blocked."""
        return rt.manual_treat()

    @app.post("/api/feeder/test", tags=["live"])
    def test_treat():
        """'Dispense a test treat' in Settings > Feeder. Not counted for any dog."""
        return {"ok": rt.test_treat()}

    @app.post("/api/sim/pose", tags=["live"])
    def sim_pose(body: SimPoseIn):
        """Mock mode only: force the simulated dog's pose (``auto`` lets it move on its own)."""
        try:
            rt.set_sim_pose(body.pose)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))
        return {"pose": body.pose}

    @app.get("/api/snapshot.jpg", tags=["live"])
    def snapshot():
        frame, st = rt.latest_frame()
        jpeg = encode_jpeg(render_frame(frame, st))
        if jpeg is None:
            raise HTTPException(503, "No frame yet")
        return Response(content=jpeg, media_type="image/jpeg")

    @app.get("/api/video", tags=["live"])
    async def video(request: Request):
        """MJPEG stream of the camera with the detection box (use it as an <img> src)."""
        async def frames():
            while not await request.is_disconnected():
                frame, st = rt.latest_frame()
                jpeg = encode_jpeg(render_frame(frame, st))
                if jpeg:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(1 / VIDEO_FPS)
        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    # ------------------------------------------------------------------ dogs & exercises
    @app.get("/api/exercises", tags=["dogs"])
    def exercises():
        return [{"id": e.id, "name": e.name, "pose": e.pose, "base_hold_s": e.base_hold_s,
                 "max_hold_s": e.max_hold_s, "learnable": e.learnable, "requires": e.requires,
                 "detectable": e.detectable} for e in plan.EXERCISES.values()]

    @app.get("/api/dogs", tags=["dogs"])
    def list_dogs():
        """All dogs with today's numbers, 7-day stats, exercises and today's caught moments."""
        return [rt.dog_detail(d) for d in store.dogs()]

    @app.post("/api/dogs", status_code=201, tags=["dogs"])
    def add_dog(body: DogIn):
        dog = store.add_dog(Dog(**body.model_dump()))
        if rt.dog_id is None:
            rt.select_dog(dog.id)
        return rt.dog_detail(dog)

    @app.get("/api/dogs/{dog_id}", tags=["dogs"])
    def dog_detail(dog_id: int):
        return rt.dog_detail(get_dog(dog_id))

    @app.patch("/api/dogs/{dog_id}", tags=["dogs"])
    def update_dog(dog_id: int, body: DogPatch):
        get_dog(dog_id)
        return rt.dog_detail(store.update_dog(dog_id, body.model_dump(exclude_unset=True)))

    @app.delete("/api/dogs/{dog_id}", tags=["dogs"])
    def archive_dog(dog_id: int):
        """Archives the dog (its history stays in the database)."""
        get_dog(dog_id)
        rt.archive_dog(dog_id)
        return {"ok": True}

    @app.post("/api/dogs/{dog_id}/select", tags=["dogs"])
    def select_dog(dog_id: int):
        """The dog being trained in Live (limits, schedules and stats use this dog)."""
        rt.select_dog(get_dog(dog_id).id)
        return {"dog_id": dog_id}

    @app.patch("/api/dogs/{dog_id}/exercises/{exercise_id}", tags=["dogs"])
    def set_exercise_stage(dog_id: int, exercise_id: str, body: StageIn):
        """Moves an exercise between stages (e.g. 'Move to step 2' -> train)."""
        dog = get_dog(dog_id)
        if exercise_id not in plan.EXERCISES:
            raise HTTPException(404, "Exercise not found")
        p = store.progress(dog.id, exercise_id)
        p.stage = body.stage
        if body.stage != "next" and p.started_at is None:
            p.started_at = rt.wall()
        store.save_progress(p)
        return p.to_dict()

    # ------------------------------------------------------------------ schedules
    @app.get("/api/schedules", tags=["schedules"])
    def list_schedules(dog_id: Optional[int] = None):
        return [s.to_dict() for s in store.schedules(dog_id)]

    @app.post("/api/schedules", status_code=201, tags=["schedules"])
    def add_schedule(body: ScheduleIn):
        get_dog(body.dog_id)
        try:
            s = store.add_schedule(Schedule(**body.model_dump()))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        rt.invalidate_schedules()
        return s.to_dict()

    @app.patch("/api/schedules/{schedule_id}", tags=["schedules"])
    def update_schedule(schedule_id: int, body: SchedulePatch):
        get_schedule(schedule_id)
        try:
            s = store.update_schedule(schedule_id, body.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        rt.invalidate_schedules()
        return s.to_dict()

    @app.delete("/api/schedules/{schedule_id}", tags=["schedules"])
    def delete_schedule(schedule_id: int):
        get_schedule(schedule_id)
        store.delete_schedule(schedule_id)
        rt.invalidate_schedules()
        return {"ok": True}

    # ------------------------------------------------------------------ highlights
    @app.get("/api/highlights", tags=["highlights"])
    def list_highlights(dog_id: Optional[int] = None, limit: int = 50):
        return store.highlights(dog_id, limit=max(1, min(limit, 200)))

    @app.get("/api/highlights/{highlight_id}/clip", tags=["highlights"])
    def highlight_clip(highlight_id: int):
        h = store.highlight(highlight_id)
        if not h or not h["clip_path"] or not Path(h["clip_path"]).exists():
            raise HTTPException(404, "Clip not available")
        return FileResponse(h["clip_path"], media_type="video/mp4")

    # ------------------------------------------------------------------ settings, events, stats
    @app.get("/api/settings", tags=["settings"])
    def get_settings():
        return rt.settings.current.to_dict()

    @app.patch("/api/settings", tags=["settings"])
    def update_settings(body: SettingsPatch):
        return rt.settings.update(body.model_dump(exclude_unset=True)).to_dict()

    @app.get("/api/events", tags=["stats"])
    def events(dog_id: Optional[int] = None, limit: int = 30):
        return rt.event_log.recent(max(1, min(limit, 500)), dog_id=dog_id)

    @app.get("/api/stats/daily", tags=["stats"])
    def stats_daily(dog_id: Optional[int] = None, days: int = 7):
        """One row per day (oldest first). Without dog_id: all dogs together."""
        return rt.event_log.daily(max(1, min(days, 60)), dog_id=dog_id)

    # ------------------------------------------------------------------ the app itself
    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="app")

    return app
