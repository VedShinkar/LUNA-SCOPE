from pydantic import BaseModel, Field
from typing import Optional, Any


class CopilotRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None


class CopilotResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    tools_used: list[Any] = Field(default_factory=list)
    evidence: list[Any] = Field(default_factory=list)
    data_notice: Optional[str] = None
    error: Optional[str] = None