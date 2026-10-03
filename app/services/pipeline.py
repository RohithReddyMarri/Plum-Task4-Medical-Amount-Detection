from typing import Optional, Union, Dict, Any
from app.schemas import (
    Step1Response,
    Step2Response,
    Step3Response,
    Step4Response,
    GuardrailExitResponse,
    PipelineExecutionResponse,
)
from app.services.ocr_service import OCRService
from app.services.normalizer import NormalizerService
from app.services.context_classifier import ContextClassifierService
from app.services.ai_extractor import AIExtractorService
from app.services.guardrails import GuardrailsService


class PipelineCoordinator:
    @classmethod
    def run_full_pipeline(
        cls,
        text: Optional[str] = None,
        image_bytes: Optional[bytes] = None
    ) -> Union[Step4Response, GuardrailExitResponse, PipelineExecutionResponse]:
        """
        Executes the end-to-end 4-step pipeline with guardrails.
        """
        input_type = "image" if image_bytes else "text"

        # --- STEP 1: OCR / Text Extraction ---
        step1_res, guardrail_exit, raw_text = OCRService.process_step1(text=text, image_bytes=image_bytes)
        if guardrail_exit:
            return guardrail_exit

        # Guardrail check on Step 1 output
        tokens_exit = GuardrailsService.check_amounts_extracted(step1_res.raw_tokens)
        if tokens_exit:
            return tokens_exit

        # --- STEP 2: Normalization ---
        step2_res = NormalizerService.process_step2(
            raw_tokens=step1_res.raw_tokens,
            step1_confidence=step1_res.confidence
        )

        if not step2_res.normalized_amounts:
            return GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")

        # --- STEP 3: Classification by Context ---
        step3_res = ContextClassifierService.process_step3(
            raw_text=raw_text,
            normalized_amounts=step2_res.normalized_amounts,
            step2_confidence=step2_res.normalization_confidence
        )

        # Optional AI Chaining & Semantic Validation
        if AIExtractorService.is_ai_available():
            ai_data = AIExtractorService.extract_with_gemini(raw_text)
            if ai_data and "amounts" in ai_data:
                # Merge or cross-validate AI extraction
                pass

        # --- STEP 4: Final Output with Provenance ---
        step4_res = ContextClassifierService.process_step4(
            currency=step1_res.currency_hint,
            classified_amounts=step3_res.amounts,
            raw_text=raw_text
        )

        return step4_res

    @classmethod
    def run_detailed_pipeline(
        cls,
        text: Optional[str] = None,
        image_bytes: Optional[bytes] = None
    ) -> PipelineExecutionResponse:
        """
        Executes all 4 steps and returns the intermediate state of each stage.
        Ideal for debugging, auditing, and the interactive web demo.
        """
        input_type = "image" if image_bytes else "text"
        notes = []

        # Step 1
        step1_res, guardrail_exit, raw_text = OCRService.process_step1(text=text, image_bytes=image_bytes)
        if guardrail_exit:
            return PipelineExecutionResponse(
                status="guardrail_triggered",
                input_type=input_type,
                extracted_text=raw_text,
                step1_ocr=guardrail_exit,
                guardrails_passed=False,
                guardrail_notes=[guardrail_exit.reason]
            )

        notes.append(f"Step 1 completed: Extracted {len(step1_res.raw_tokens)} raw tokens with currency hint '{step1_res.currency_hint}'.")

        # Step 2
        step2_res = NormalizerService.process_step2(
            raw_tokens=step1_res.raw_tokens,
            step1_confidence=step1_res.confidence
        )
        if not step2_res.normalized_amounts:
            exit_resp = GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")
            return PipelineExecutionResponse(
                status="guardrail_triggered",
                input_type=input_type,
                extracted_text=raw_text,
                step1_ocr=step1_res,
                step2_normalization=step2_res,
                guardrails_passed=False,
                guardrail_notes=["No valid amounts remaining after normalization"]
            )
        notes.append(f"Step 2 completed: Repaired OCR digit errors and normalized {len(step2_res.normalized_amounts)} clean amounts.")

        # Step 3
        step3_res = ContextClassifierService.process_step3(
            raw_text=raw_text,
            normalized_amounts=step2_res.normalized_amounts,
            step2_confidence=step2_res.normalization_confidence
        )
        notes.append(f"Step 3 completed: Classified {len(step3_res.amounts)} amounts by surrounding context.")

        # Step 4
        step4_res = ContextClassifierService.process_step4(
            currency=step1_res.currency_hint,
            classified_amounts=step3_res.amounts,
            raw_text=raw_text
        )
        if step4_res.mathematical_reconciliation:
            notes.append(f"Mathematical reconciliation: {step4_res.mathematical_reconciliation['status']}")

        return PipelineExecutionResponse(
            status="ok",
            input_type=input_type,
            extracted_text=raw_text,
            step1_ocr=step1_res,
            step2_normalization=step2_res,
            step3_classification=step3_res,
            step4_final=step4_res,
            guardrails_passed=True,
            guardrail_notes=notes
        )
