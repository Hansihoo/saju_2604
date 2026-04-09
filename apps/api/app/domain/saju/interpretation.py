from typing import List, Literal

from pydantic import BaseModel


InterpretationLocale = Literal["ko", "en"]


class InterpretationNarrative(BaseModel):
    schema_version: Literal["m2-fallback-v1"] = "m2-fallback-v1"
    locale: InterpretationLocale
    summary: str
    strengths: List[str]
    cautions: List[str]
    love: str
    career: str
    wealth: str
    action_advice: str
