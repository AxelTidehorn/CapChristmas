"""Validated provider contracts. Model prose is data, never code or instructions."""
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = "medeltomten-v2.0"
PROMPT_VERSION = "consensus-match-1"
FEATURES = ("hat", "beard", "nose", "eyes", "torso", "arms", "legs", "accessories")
COMPOSITIONS = ("head_only", "bust", "full_body", "other", "uncertain")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Feature(StrictModel):
    key: Literal["hat", "beard", "nose", "eyes", "torso", "arms", "legs", "accessories"]
    presence: Literal["yes", "no", "uncertain"]
    notes: str = Field(max_length=240)


class Observation(StrictModel):
    id: str = Field(pattern=r"^d\d{4}$|^reference$")
    composition: Literal["head_only", "bust", "full_body", "other", "uncertain"]
    pose: Literal["front", "side", "other", "uncertain"]
    hat_shape: Literal["drooping", "pointed", "round", "none", "other", "uncertain"]
    beard_shape: Literal["long", "short", "round", "none", "other", "uncertain"]
    head_fraction: float | None = Field(ge=0, le=1)
    width_height_ratio: float | None = Field(ge=0.05, le=5)
    features: list[Feature]
    description: str = Field(max_length=500)

    @model_validator(mode="after")
    def unique_features(self):
        if sorted(f.key for f in self.features) != sorted(FEATURES):
            raise ValueError("Each feature must occur exactly once")
        return self


class Observations(StrictModel):
    observations: list[Observation]


class Comparison(StrictModel):
    # Ordinal rubric, NOT probabilities. 0=conflicting, 1=weak, 2=mixed, 3=close, 4=very close.
    composition: int = Field(ge=0, le=4)
    silhouette: int = Field(ge=0, le=4)
    proportions: int = Field(ge=0, le=4)
    features: int = Field(ge=0, le=4)
    reliable: bool
    explanation: str = Field(min_length=1, max_length=500)


# The three seams required by V2; provider construction lives in providers.py only.
class UnderstandingProvider(Protocol):
    def observe(self, images: list[tuple[str, bytes]]) -> tuple[Observations, dict]: ...


class GenerationProvider(Protocol):
    def generate(self, prompt: str, images: list[tuple[str, bytes]]) -> tuple[bytes, dict]: ...


class MatchingProvider(Protocol):
    def compare(self, reference: bytes, candidate: bytes, reverse: bool) -> tuple[Comparison, dict]: ...
