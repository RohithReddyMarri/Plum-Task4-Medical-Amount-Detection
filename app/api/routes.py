from typing import Optional, Union, List
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from app.schemas import (
    TextInputRequest,
    Step1Response,
    Step2Response,
    Step3Response,
    Step4Response,
    GuardrailExitResponse,
    PipelineExecutionResponse,
    AmountItem
)
from app.services.ocr_service import OCRService
from app.services.normalizer import NormalizerService
from app.services.context_classifier import ContextClassifierService
from app.services.pipeline import PipelineCoordinator

router = APIRouter(prefix="/api", tags=["Amount Detection Pipeline"])


async def _extract_input(request: Request) -> tuple[Optional[str], Optional[bytes]]:
    raw_text = None
    image_bytes = None
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            raw_text = body.get("text")
        except Exception:
            pass
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        if "file" in form:
            file_field = form["file"]
            if hasattr(file_field, "read"):
                image_bytes = await file_field.read()
        if "text" in form and form["text"]:
            raw_text = str(form["text"])
    else:
        try:
            body = await request.json()
            raw_text = body.get("text")
        except Exception:
            pass

    return raw_text, image_bytes


@router.post("/process", response_model=Union[Step4Response, GuardrailExitResponse], summary="Process Medical Document (Final Output)")
async def process_document(request: Request):
    """
    Primary processing endpoint:
    Accepts typed text (JSON body or form data) or image file upload.
    Executes the 4-step pipeline and returns the final standardized JSON (Step 4) or Guardrail exit.
    """
    raw_text, image_bytes = await _extract_input(request)

    if not raw_text and not image_bytes:
        raise HTTPException(status_code=400, detail="Either 'text' or 'file' must be provided.")

    return PipelineCoordinator.run_full_pipeline(text=raw_text, image_bytes=image_bytes)


@router.post("/pipeline", response_model=PipelineExecutionResponse, summary="Execute Full 4-Step Pipeline with Traces")
async def execute_pipeline(request: Request):
    """
    Executes the pipeline and returns the full intermediate step trace (Steps 1 to 4)
    along with confidence scores, guardrail evaluations, and mathematical checks.
    """
    raw_text, image_bytes = await _extract_input(request)

    if not raw_text and not image_bytes:
        raise HTTPException(status_code=400, detail="Either 'text' or 'file' must be provided.")

    return PipelineCoordinator.run_detailed_pipeline(text=raw_text, image_bytes=image_bytes)


# --- INDIVIDUAL STEP ENDPOINTS ---

@router.post("/step1-ocr", response_model=Union[Step1Response, GuardrailExitResponse], summary="Step 1: OCR / Text Extraction")
async def step1_ocr_endpoint(request: Request):
    """
    Step 1: Ingests text/image and extracts raw numeric tokens and currency hint.
    """
    raw_text, image_bytes = await _extract_input(request)
    step1_res, guardrail_exit, _ = OCRService.process_step1(text=raw_text, image_bytes=image_bytes)
    return guardrail_exit if guardrail_exit else step1_res


@router.post("/step2-normalize", response_model=Step2Response, summary="Step 2: Numeric Normalization")
async def step2_normalize_endpoint(raw_tokens: List[str]):
    """
    Step 2: Normalizes raw tokens, fixes OCR digit errors, and removes non-amounts.
    """
    return NormalizerService.process_step2(raw_tokens=raw_tokens)


@router.post("/step3-classify", response_model=Step3Response, summary="Step 3: Classification by Context")
async def step3_classify_endpoint(
    text: str = Form(...),
    normalized_amounts: List[float] = Form(...)
):
    """
    Step 3: Uses context to label amounts (total_bill, paid, due, etc.).
    """
    return ContextClassifierService.process_step3(raw_text=text, normalized_amounts=normalized_amounts)


@router.post("/step4-final", response_model=Step4Response, summary="Step 4: Final JSON with Provenance")
async def step4_final_endpoint(
    currency: str = Form("INR"),
    text: str = Form(...)
):
    """
    Step 4: Produces final schema with provenance text sources.
    """
    step1_res, _, _ = OCRService.process_step1(text=text)
    if not step1_res:
        raise HTTPException(status_code=400, detail="Could not parse amounts")
    step2_res = NormalizerService.process_step2(step1_res.raw_tokens)
    step3_res = ContextClassifierService.process_step3(text, step2_res.normalized_amounts)
    return ContextClassifierService.process_step4(currency, step3_res.amounts, text)
