from typing import List, Optional, Union
from pydantic import BaseModel, Field


class TextInputRequest(BaseModel):
    """Input payload when submitting raw or noisy text."""
    text: str = Field(..., description="Raw text of medical bill or OCR string", examples=["Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"])


# --- Guardrail Response ---
class GuardrailExitResponse(BaseModel):
    """Exit condition returned when document is too noisy or no amounts are detected."""
    status: str = Field(default="no_amounts_found", examples=["no_amounts_found"])
    reason: str = Field(default="document too noisy", examples=["document too noisy"])


# --- Step 1: OCR / Text Extraction ---
class Step1Response(BaseModel):
    """Step 1 output: Raw numeric tokens and currency hint extracted from text or image."""
    raw_tokens: List[str] = Field(..., description="Raw numeric and percentage tokens found", examples=[["1200", "1000", "200", "10%"]])
    currency_hint: str = Field(default="INR", description="Inferred currency hint", examples=["INR"])
    confidence: float = Field(..., description="Extraction confidence score (0.0 - 1.0)", examples=[0.74])


# --- Step 2: Normalization ---
class Step2Response(BaseModel):
    """Step 2 output: Normalized clean monetary numbers with OCR digit corrections applied."""
    normalized_amounts: List[Union[int, float]] = Field(..., description="Clean numeric amounts with OCR errors repaired", examples=[[1200, 1000, 200]])
    normalization_confidence: float = Field(..., description="Confidence score after normalization", examples=[0.82])


# --- Step 3: Classification by Context ---
class AmountItem(BaseModel):
    type: str = Field(..., description="Classification category (e.g., total_bill, paid, due, discount)", examples=["total_bill"])
    value: Union[int, float] = Field(..., description="Numeric value of the amount", examples=[1200])


class Step3Response(BaseModel):
    """Step 3 output: Contextually classified amounts."""
    amounts: List[AmountItem] = Field(..., description="Amounts labeled by context")
    confidence: float = Field(..., description="Classification confidence score", examples=[0.80])


# --- Step 4: Final Output with Provenance ---
class FinalAmountItem(BaseModel):
    type: str = Field(..., description="Financial role of amount (total_bill, paid, due, etc.)", examples=["total_bill"])
    value: Union[int, float] = Field(..., description="Monetary value", examples=[1200])
    source: str = Field(..., description="Audit provenance showing origin text segment", examples=["text: 'Total: INR 1200'"])


class Step4Response(BaseModel):
    """Step 4 output: Standardized final JSON adhering precisely to assignment specifications."""
    currency: str = Field(default="INR", examples=["INR"])
    amounts: List[FinalAmountItem] = Field(...)
    status: str = Field(default="ok", examples=["ok"])
    # Bonus enterprise guardrail: Financial reconciliation check
    mathematical_reconciliation: Optional[dict] = Field(
        default=None,
        description="Verification check: Does total_bill match paid + due?"
    )


# --- Comprehensive Pipeline Response ---
class PipelineExecutionResponse(BaseModel):
    """Combined output containing every pipeline stage plus final response."""
    status: str = Field(examples=["ok"])
    input_type: str = Field(examples=["text"])
    extracted_text: Optional[str] = Field(default=None)
    step1_ocr: Union[Step1Response, GuardrailExitResponse]
    step2_normalization: Optional[Step2Response] = None
    step3_classification: Optional[Step3Response] = None
    step4_final: Optional[Step4Response] = None
    guardrails_passed: bool = Field(default=True)
    guardrail_notes: List[str] = Field(default_factory=list)
