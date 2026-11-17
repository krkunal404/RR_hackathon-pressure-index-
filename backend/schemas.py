"""Pydantic response models for the stable, typed parts of the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

Role = Literal["batters", "bowlers"]


class Overview(BaseModel):
    matches: int
    ipl_matches: int
    t20i_matches: int
    deliveries: int
    players: int
    batters: int
    bowlers: int
    pressure_deliveries: int
    high_deliveries: int
    extreme_deliveries: int
    eligible_batters: int
    eligible_bowlers: int
    seasons: list[int]
    generated_at: str


class Filters(BaseModel):
    competitions: list[str]
    seasons: list[int]
    teams: list[str]
    pressure_categories: list[str]
    phases: list[str]


class PlayerRow(BaseModel):
    model_config = {"extra": "allow"}
    player_id: int
    name: str | None = None
    team: str | None = None
    rank: float | None = None
    rating: float | None = None
    reliability: float | None = None
    eligible: bool


class RankingResponse(BaseModel):
    role: Role
    competition: str
    count: int
    rows: list[dict[str, Any]]


class PlayerProfile(BaseModel):
    role: Role
    player: dict[str, Any]
    components: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    by_category: list[dict[str, Any]]
    by_phase: list[dict[str, Any]]
    by_chase: list[dict[str, Any]]
    by_season: list[dict[str, Any]]
    competition_split: list[dict[str, Any]]
