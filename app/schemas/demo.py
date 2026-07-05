from pydantic import BaseModel, Field

from app.schemas.anti_spoofing import AntiSpoofingResponse


class DemoStartResponse(BaseModel):
    """Response for starting a no-cost sample-based voice phishing demo."""

    session_id: str = Field(..., examples=["f2b7be64db3049858e248802d9500958"])
    audio_url: str = Field(
        ...,
        examples=["/api/v1/demo-sessions/f2b7be64db3049858e248802d9500958/audio"],
    )
    playback_seconds: int = Field(..., examples=[10])
    message: str = Field(..., examples=["demo_session_started"])


class DemoAnswerRequest(BaseModel):
    """User guess for a demo sample."""

    user_guess: str = Field(
        ...,
        description="real or fake",
        examples=["fake"],
    )


class DemoAnswerResponse(BaseModel):
    """Result after comparing the user guess with IsFAM AI judgment."""

    session_id: str
    user_guess: str
    actual_label: str
    is_user_correct: bool
    ai_guess: str
    is_ai_correct: bool
    anti_spoofing: AntiSpoofingResponse
    message: str = Field(..., examples=["demo_answer_evaluated"])
