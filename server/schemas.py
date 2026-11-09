"""Request bodies for the API. Responses are plain dicts built by src.app_runtime."""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Stage = Literal["next", "learn", "train", "mastered"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")       # unknown fields -> 422 instead of being ignored


class CommandIn(Strict):
    exercise: str = Field(description="sit | down | stand | stay (or a posture label: sitting, lying...)")


class SimPoseIn(Strict):
    pose: Literal["sitting", "standing", "lying", "none", "auto"]


class DogIn(Strict):
    name: str = Field(min_length=1, max_length=40)
    breed: Optional[str] = None
    birth_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    weight_kg: Optional[float] = Field(None, gt=0)
    color: Optional[str] = None
    daily_treat_limit: int = Field(20, ge=0, le=500)
    pronoun: Literal["he", "she"] = "he"


class DogPatch(Strict):
    name: Optional[str] = Field(None, min_length=1, max_length=40)
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    weight_kg: Optional[float] = Field(None, gt=0)
    color: Optional[str] = None
    daily_treat_limit: Optional[int] = Field(None, ge=0, le=500)
    pronoun: Optional[Literal["he", "she"]] = None


class StageIn(Strict):
    stage: Stage


class ScheduleIn(Strict):
    dog_id: int
    kind: Literal["learn", "train"]
    exercise_ids: List[str] = Field(min_length=1)
    days: List[int] = Field(default_factory=lambda: list(range(7)), description="0 = Monday")
    start: Optional[str] = Field(None, description="learn: HH:MM")
    end: Optional[str] = Field(None, description="learn: HH:MM")
    times: List[str] = Field(default_factory=list, description="train: [HH:MM, ...]")
    reps: int = Field(10, ge=1, le=50)
    max_treats: int = Field(10, ge=0, le=200)
    min_interval_s: float = Field(1800.0, ge=0)
    enabled: bool = True


class SchedulePatch(Strict):
    exercise_ids: Optional[List[str]] = None
    days: Optional[List[int]] = None
    start: Optional[str] = None
    end: Optional[str] = None
    times: Optional[List[str]] = None
    reps: Optional[int] = Field(None, ge=1, le=50)
    max_treats: Optional[int] = Field(None, ge=0, le=200)
    min_interval_s: Optional[float] = Field(None, ge=0)
    enabled: Optional[bool] = None


class SettingsPatch(Strict):
    """Device-wide settings (src.config.AppSettings). Send only what changes."""
    passive_enabled: Optional[bool] = None
    passive_poses: Optional[List[Literal["sitting", "standing", "lying"]]] = None
    passive_pose_cooldown_s: Optional[float] = Field(None, ge=0)
    passive_sound_when_treat_blocked: Optional[bool] = None
    active_command_timeout_s: Optional[float] = Field(None, gt=0, le=60)
    active_command_play_cue: Optional[bool] = None
    active_command_reward: Optional[bool] = None
    daily_treat_limit: Optional[int] = Field(None, ge=0, le=1000)
    min_seconds_between_treats: Optional[float] = Field(None, ge=0)
    volume: Optional[float] = Field(None, ge=0, le=1)
