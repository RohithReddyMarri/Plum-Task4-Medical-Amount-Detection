from typing import List, Dict, Any, Optional
from app.schemas import GuardrailExitResponse


class GuardrailsService:
    @staticmethod
    def check_noisy_document(raw_text: str, confidence: float, min_threshold: float = 0.30) -> Optional[GuardrailExitResponse]:
        """
        Guardrail: Validates whether document is legible or excessively degraded/noisy.
        """
        if not raw_text or not raw_text.strip():
            return GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")

        # Check alphanumeric content
        alphanumeric_chars = sum(c.isalnum() for c in raw_text)
        if alphanumeric_chars < 3:
            return GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")

        if confidence < min_threshold:
            return GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")

        return None

    @staticmethod
    def check_amounts_extracted(raw_tokens: List[str]) -> Optional[GuardrailExitResponse]:
        """
        Guardrail: Validates that numeric tokens were successfully identified.
        """
        if not raw_tokens:
            return GuardrailExitResponse(status="no_amounts_found", reason="document too noisy")
        return None

    @staticmethod
    def check_financial_reconciliation(total: Optional[float], paid: Optional[float], due: Optional[float]) -> Dict[str, Any]:
        """
        Guardrail: Mathematical integrity validation (Total == Paid + Due).
        """
        if total is None or paid is None or due is None:
            return {"status": "skipped", "message": "Incomplete triplet for math reconciliation"}

        discrepancy = round(total - (paid + due), 2)
        if abs(discrepancy) < 0.01:
            return {
                "status": "passed",
                "message": f"Mathematical balance verified: {total} == {paid} + {due}",
                "is_balanced": True,
                "discrepancy": 0.0
            }
        else:
            return {
                "status": "warning",
                "message": f"Mathematical mismatch: Total ({total}) != Paid ({paid}) + Due ({due}), delta: {discrepancy}",
                "is_balanced": False,
                "discrepancy": discrepancy
            }
