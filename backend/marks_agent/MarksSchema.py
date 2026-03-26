from typing import List
from pydantic import BaseModel, Field

class MarksSchema(BaseModel):
    green: List[int] = Field(default_factory=list)
    yellow: List[int] = Field(default_factory=list)
    red: List[int] = Field(default_factory=list)