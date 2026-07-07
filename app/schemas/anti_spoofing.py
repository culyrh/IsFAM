from pydantic import BaseModel, ConfigDict, Field


class AntiSpoofingLabelScore(BaseModel):
    label: str = Field(..., examples=["spoof"])
    score: float = Field(..., examples=[0.91])


class AntiSpoofingResponse(BaseModel):
    """Response for one anti-spoofing/deepfake detection result."""

    model_config = ConfigDict(protected_namespaces=())

    is_spoofed: bool = Field(
        ...,
        description="True when spoof_score is greater than or equal to threshold.",
        examples=[False],
    )
    spoof_score: float = Field(
        ...,
        description="Highest segment-level combined probability of labels configured as spoof/fake labels.",
        examples=[0.12],
    )
    threshold: float = Field(..., examples=[0.5])
    predicted_label: str = Field(..., examples=["bonafide"])
    predicted_score: float = Field(..., examples=[0.88])
    message: str = Field(..., examples=["bonafide"])
    model_name: str = Field(..., examples=["Vansh180/deepfake-audio-wav2vec2"])
    analyzed_segments: int = Field(
        ...,
        description="Number of audio windows analyzed for anti-spoofing.",
        examples=[3],
    )
    max_spoof_segment_index: int = Field(
        ...,
        description="Zero-based index of the segment that produced spoof_score.",
        examples=[1],
    )
    segment_seconds: float = Field(
        ...,
        description="Window length used for segment-level anti-spoofing.",
        examples=[5.0],
    )
    label_scores: list[AntiSpoofingLabelScore] = Field(
        ...,
        description="Label scores from the segment that produced spoof_score.",
    )
