from typing import List, Optional
from pydantic import BaseModel, Field
from .MarksSchema import MarksSchema

class StudentPayload(BaseModel):
    student_id: str
    total_fragments: int
    marks: MarksSchema = Field(default_factory=MarksSchema)
    ground_truth_errors: Optional[List[int]] = None