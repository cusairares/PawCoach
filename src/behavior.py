"""Behavior controller: passive capture + one-shot active commands.

Passive capture
    When the dog *newly* enters a pose (confirmed by the strict passive tracker) and
    holds it for ``passive_dwell_s``, play that pose's cue word + the marker sound and
    dispense a treat - subject to the app's limits (daily budget, min interval between
    treats, per-pose cooldown). Edge-triggered: one capture per pose entry.

Active command (executed exactly once, parameters come from the app)
    1. play the cue for the target pose
    2. wait up to ``timeout_s`` for the dog to *transition into* the target pose
       (already holding it at cue time does not count - the tracker's entry_id must
       increase after the cue) and hold it for ``active_dwell_s``
    3. success -> marker + treat (if allowed);  timeout -> logged failure
    Passive capture is suspended while a command runs. A command arriving while
    another is running is rejected ("busy"); the app decides what to do.

App features (multi-dog, schedules, Stay)
    * ``context`` - set by the runtime: which dog is being trained (``dog_id``), which
      schedule is running (``schedule_id``) and optional passive overrides
      (``passive_enabled`` / ``passive_poses``) for scheduled learning windows.
      Every logged event is tagged with dog_id / schedule_id.
    * ``treat_guard(now, context) -> (ok, reason)`` - extra treat rules on top of the
      device-wide ones (per-dog daily limit, per-schedule max treats / min interval).
    * A command may carry ``hold_s`` (how long the pose must be held, e.g. Stay = 5 s)
      and ``dog_id`` / ``schedule_id``; see ``src/training_plan.TrainingCommand``.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .config import POSE_TO_CUE, CommandRequest, EngineConfig, SettingsStore
from .consensus import StateTracker
from .event_log import Event, EventLog, start_of_day

log = logging.getLogger(__name__)


@dataclass
class ActiveCommand:
    request: CommandRequest
    started_at: float
    entry_id_at_start: int


class BehaviorController:
    def __init__(self, audio, feeder, event_log: EventLog, settings: SettingsStore,
                 config: EngineConfig, wall_clock: Callable[[], float] = time.time,
                 treat_guard: Optional[Callable[[float, Dict], Tuple[bool, str]]] = None):
        self.audio, self.feeder, self.event_log = audio, feeder, event_log
        self.settings, self.config, self.wall_clock = settings, config, wall_clock
        self.treat_guard = treat_guard
        self.context: Dict = {}
        self._commands: "queue.Queue[CommandRequest]" = queue.Queue()
        self._cancel = threading.Event()
        self.active: Optional[ActiveCommand] = None
        self._passive_handled_entry = 0
        self._last_capture: Dict[str, float] = {}
        self._last_treat: Optional[float] = None
        self.last_events: List[Event] = []

    # ---- thread-safe API used by the app / keyboard -------------------------------
    def submit(self, request: CommandRequest) -> str:
        self._commands.put(request)
        return request.command_id

    def cancel(self) -> None:
        self._cancel.set()

    # ---- called once per processed frame by the pipeline ---------------------------
    def update(self, now: float, passive: StateTracker, active: StateTracker) -> List[Event]:
        events: List[Event] = []
        if self._cancel.is_set():
            self._cancel.clear()
            if self.active:
                events.append(self._finish(now, passive, "command_fail", active, detail="cancelled"))

        while True:
            try:
                req = self._commands.get_nowait()
            except queue.Empty:
                break
            if self.active:
                events.append(self._log(Event("command_rejected", target=req.pose,
                                              command_id=req.command_id, detail="busy")))
                continue
            self.active = ActiveCommand(req, now, active.entry_id)
            current_settings = self.settings.current
            if current_settings.active_command_play_cue:
                self.audio.play([POSE_TO_CUE[req.pose]])
            log.info("[command] %s started (timeout %.1fs)", req.pose, current_settings.active_command_timeout_s)

        if self.active:
            events.extend(self._update_command(now, passive, active))
        else:
            events.extend(self._update_passive(now, passive))
        self.last_events = events
        return events

    # ---- internals -----------------------------------------------------------------
    def _update_command(self, now: float, passive: StateTracker, active: StateTracker) -> List[Event]:
        cmd = self.active
        req = cmd.request
        s = self.settings.current
        entered_after_cue = active.entry_id > cmd.entry_id_at_start
        hold_s = getattr(req, "hold_s", None) or self.config.active_dwell_s   # per-command hold (Stay)
        if (active.state == req.pose and entered_after_cue
                and active.held_for(now) >= hold_s):
            self.audio.play(["marker"])
            treat, reason = False, "reward_disabled"
            if s.active_command_reward:
                treat, reason = self._try_treat(now, "command")
            return [self._finish(now, passive, "command_success", active,
                                 reaction_s=active.since - cmd.started_at, treat=treat,
                                 detail=None if treat else reason)]
        if now - cmd.started_at >= s.active_command_timeout_s:
            return [self._finish(now, passive, "command_fail", active, detail="timeout")]
        return []

    def _finish(self, now: float, passive: StateTracker, kind: str, active: StateTracker,
                reaction_s: Optional[float] = None, treat: bool = False,
                detail: Optional[str] = None) -> Event:
        req = self.active.request
        self.active = None
        # The pose held at the end of a command must not be re-rewarded by passive mode.
        self._passive_handled_entry = passive.entry_id
        log.info("[command] %s -> %s (%s)", req.pose, kind, detail or "ok")
        return self._log(Event(kind, target=req.pose, detected=active.state, reaction_s=reaction_s,
                               treat=treat, command_id=req.command_id, detail=detail,
                               dog_id=getattr(req, "dog_id", None),
                               schedule_id=getattr(req, "schedule_id", None)))

    def _update_passive(self, now: float, passive: StateTracker) -> List[Event]:
        s = self.settings.current
        pose = passive.state
        # Scheduled learning windows may override the app-wide passive settings.
        enabled = self.context.get("passive_enabled", s.passive_enabled)
        poses = self.context.get("passive_poses", s.passive_poses)
        if (not enabled or pose not in poses
                or passive.entry_id == self._passive_handled_entry
                or passive.held_for(now) < self.config.passive_dwell_s):
            return []
        self._passive_handled_entry = passive.entry_id          # edge-triggered
        last = self._last_capture.get(pose)
        if last is not None and now - last < s.passive_pose_cooldown_s:
            return []
        treat, reason = self._try_treat(now, "passive")
        if not treat and not s.passive_sound_when_treat_blocked:
            return [self._log(Event("passive_capture", target=pose, detected=pose,
                                    treat=False, detail=f"silent:{reason}"))]
        self.audio.play([POSE_TO_CUE[pose], "marker"])
        self._last_capture[pose] = now
        return [self._log(Event("passive_capture", target=pose, detected=pose, treat=treat,
                                detail=None if treat else reason))]

    def treats_today(self) -> int:
        return self.event_log.treats_since(start_of_day(self.wall_clock()))

    def _try_treat(self, now: float, source: str) -> Tuple[bool, str]:
        """``source``: passive | command | manual (the treat guard can treat them differently)."""
        s = self.settings.current
        if self.treats_today() >= s.daily_treat_limit:
            return False, "daily_limit"
        if self._last_treat is not None and now - self._last_treat < s.min_seconds_between_treats:
            return False, "min_interval"
        if self.treat_guard is not None:                    # per-dog / per-schedule limits
            ok, reason = self.treat_guard(now, {**self.context, "source": source})
            if not ok:
                return False, reason
        if not self.feeder.dispense():
            return False, "feeder_error"
        self._last_treat = now
        return True, "ok"

    def give_treat(self, now: float) -> Tuple[bool, str]:
        """Manual treat from the app (Treat button). Same limits as automatic treats."""
        treat, reason = self._try_treat(now, "manual")
        self._log(Event("manual_treat", treat=treat, detail=None if treat else reason))
        return treat, reason

    def _log(self, event: Event) -> Event:
        event.ts = self.wall_clock()
        if event.dog_id is None:
            event.dog_id = self.context.get("dog_id")
        # A learning window's schedule only covers passive captures; a training session covers all.
        if event.schedule_id is None and (event.kind == "passive_capture"
                                          or self.context.get("schedule_scope", "all") == "all"):
            event.schedule_id = self.context.get("schedule_id")
        self.event_log.add(event)
        return event

    def status(self, now: float) -> Dict:
        st = {"mode": "command" if self.active else "passive", "treats_today": self.treats_today()}
        if self.active:
            req = self.active.request
            timeout = self.settings.current.active_command_timeout_s
            st.update(target=req.pose, command_id=req.command_id,
                      remaining_s=max(0.0, timeout - (now - self.active.started_at)),
                      hold_s=getattr(req, "hold_s", None) or self.config.active_dwell_s,
                      exercise_id=getattr(req, "exercise_id", None))
        return st
