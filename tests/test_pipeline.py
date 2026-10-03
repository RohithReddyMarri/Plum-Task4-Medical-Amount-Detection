import pytest
from app.services.ocr_service import OCRService
from app.services.normalizer import NormalizerService
from app.services.context_classifier import ContextClassifierService
from app.services.guardrails import GuardrailsService
from app.services.pipeline import PipelineCoordinator
from app.schemas import GuardrailExitResponse, Step4Response


def test_step1_text_extraction():
    text = "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"
    step1_res, guardrail, raw = OCRService.process_step1(text=text)

    assert guardrail is None
    assert step1_res is not None
    assert "1200" in step1_res.raw_tokens
    assert "1000" in step1_res.raw_tokens
    assert "200" in step1_res.raw_tokens
    assert "10%" in step1_res.raw_tokens
    assert step1_res.currency_hint == "INR"
    assert step1_res.confidence >= 0.70


def test_step2_normalization_and_ocr_correction():
    raw_tokens = ["1200", "1000", "200", "10%"]
    step2_res = NormalizerService.process_step2(raw_tokens)

    # 10% should be filtered out
    assert step2_res.normalized_amounts == [1200, 1000, 200]
    assert step2_res.normalization_confidence >= 0.80

    # Test OCR digit repairs (l200 -> 1200, 25O -> 250)
    corrupted_tokens = ["l200", "1000", "25O"]
    res_corrupted = NormalizerService.process_step2(corrupted_tokens)
    assert 1200 in res_corrupted.normalized_amounts
    assert 1000 in res_corrupted.normalized_amounts
    assert 250 in res_corrupted.normalized_amounts


def test_step3_context_classification():
    text = "Total: INR 1200 | Paid: 1000 | Due: 200"
    normalized_amounts = [1200, 1000, 200]
    step3_res = ContextClassifierService.process_step3(text, normalized_amounts)

    labels = {item.type: item.value for item in step3_res.amounts}
    assert labels.get("total_bill") == 1200
    assert labels.get("paid") == 1000
    assert labels.get("due") == 200


def test_step4_final_output_and_provenance():
    text = "Total: INR 1200 | Paid: 1000 | Due: 200"
    step1_res, _, _ = OCRService.process_step1(text=text)
    step2_res = NormalizerService.process_step2(step1_res.raw_tokens)
    step3_res = ContextClassifierService.process_step3(text, step2_res.normalized_amounts)
    step4_res = ContextClassifierService.process_step4("INR", step3_res.amounts, text)

    assert step4_res.status == "ok"
    assert step4_res.currency == "INR"
    assert len(step4_res.amounts) == 3

    # Check provenance format
    for amt in step4_res.amounts:
        assert amt.source.startswith("text: '")
        assert len(amt.source) > 8

    # Mathematical reconciliation
    assert step4_res.mathematical_reconciliation is not None
    assert step4_res.mathematical_reconciliation["is_balanced"] is True


def test_noisy_document_guardrail():
    text = "--- !!! @#$$%^ blurred noise"
    step1_res, guardrail, _ = OCRService.process_step1(text=text)

    assert step1_res is None
    assert isinstance(guardrail, GuardrailExitResponse)
    assert guardrail.status == "no_amounts_found"
    assert guardrail.reason == "document too noisy"

    # Full pipeline test with noisy input
    result = PipelineCoordinator.run_full_pipeline(text=text)
    assert isinstance(result, GuardrailExitResponse)
    assert result.status == "no_amounts_found"


def test_end_to_end_noisy_ocr_sample():
    # Exact noisy sample from assignment PDF: T0tal: Rs l200 | Pald: 1000 | Due: 200
    noisy_text = "T0tal: Rs l200 | Pald: 1000 | Due: 200"
    result = PipelineCoordinator.run_full_pipeline(text=noisy_text)

    assert isinstance(result, Step4Response)
    assert result.status == "ok"
    assert result.currency == "INR"

    val_map = {item.type: item.value for item in result.amounts}
    assert val_map["total_bill"] == 1200
    assert val_map["paid"] == 1000
    assert val_map["due"] == 200
