from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Claim(Strict):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1000)
    kind: Literal["numeric", "historical_performance", "event", "observation", "opinion"]
    evidence_id: str | None = None
    metric: str | None = None
    value: float | None = None
    relation: Literal["positive", "negative", "zero"] | None = None
    event_type: str | None = None
    event_date: str | None = None


class Point(Strict):
    text: str = Field(min_length=1, max_length=1000)
    claim_ids: list[str] = Field(default_factory=list, max_length=10)


class Output(Strict):
    content_md: str = Field(min_length=1, max_length=6000)
    stance: Literal["bullish", "bearish", "neutral", "mixed"]
    confidence: Literal["low", "medium", "high"]
    counter_argument: str = Field(min_length=1, max_length=1000)
    claims: list[Claim] = Field(max_length=12)
    key_points: list[Point] = Field(default_factory=list, max_length=8)
    risks: list[Point] = Field(default_factory=list, max_length=8)
    invalidation: list[Point] = Field(default_factory=list, max_length=6)
    excluded_claims: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_claims(self):
        if len({c.id for c in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim IDs")
        return self
