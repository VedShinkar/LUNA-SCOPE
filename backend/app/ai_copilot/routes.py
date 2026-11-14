from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.ai_copilot.agent import ask_copilot
from app.ai_copilot.schemas import CopilotRequest, CopilotResponse

router = APIRouter(
    prefix="/api/v1/copilot",
    tags=["AI Mission Copilot"]
)


@router.post("/chat", response_model=CopilotResponse)
def chat_with_copilot(request: CopilotRequest):
    """
    Send a natural-language lunar mission question
    to the AI Mission Copilot.
    """

    result = ask_copilot(
        question=request.question,
        session_id=request.session_id
    )

    if not result.get("success"):
        return JSONResponse(
            status_code=500,
            content=result
        )

    return result