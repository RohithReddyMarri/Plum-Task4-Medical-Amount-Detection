import re
from typing import List, Dict, Any, Tuple, Optional
from app.schemas import AmountItem, FinalAmountItem, Step3Response, Step4Response


class ContextClassifierService:
    # Context keyword definitions for medical bill items
    CONTEXT_PATTERNS = {
        "total_bill": [
            r'\b(?:t0tal|total|grand\s*total|gross\s*amount|bill\s*amount|net\s*payable|invoice\s*total|total\s*due)\b',
            r'\btot\b',
        ],
        "paid": [
            r'\b(?:pald|paid|amount\s*paid|advance|deposit|payment\s*received|received)\b',
            r'\bpd\b',
        ],
        "due": [
            r'\b(?:due|balance\s*due|balance|remaining|pending|outstanding|amt\s*due)\b',
        ],
        "discount": [
            r'\b(?:discount|less|rebate|concession)\b',
        ],
        "tax": [
            r'\b(?:tax|gst|cgst|sgst|vat)\b',
        ]
    }

    @classmethod
    def _find_provenance_and_label(cls, raw_text: str, amount_val: float) -> Tuple[str, str]:
        """
        Locates the surrounding text fragment (provenance) and assigns context classification.
        Handles OCR corrupted variations like 'T0tal: Rs l200' without substring collisions.
        """
        # Split text into segments by pipes, newlines, semicolons, or multiple spaces
        segments = [s.strip() for s in re.split(r'[\n\r|;]+', raw_text) if s.strip()]
        val_str = str(int(amount_val)) if isinstance(amount_val, int) or amount_val.is_integer() else str(amount_val)

        # Build regex that matches the number and its OCR variants (l for 1, O for 0)
        # Bounded by non-digits so e.g. 200 does not match inside 1200
        num_pattern_str = val_str.replace('0', '[0oO]').replace('1', '[1lI|]')
        token_regex = re.compile(rf'(?<![0-9a-zA-Z]){num_pattern_str}(?![0-9a-zA-Z])', re.IGNORECASE)

        best_label = "other"
        best_source = f"text: '{val_str}'"

        for seg in segments:
            if token_regex.search(seg):
                # Classify based on keywords in this segment
                for label, regex_list in cls.CONTEXT_PATTERNS.items():
                    for reg in regex_list:
                        if re.search(reg, seg, re.IGNORECASE):
                            best_label = label
                            best_source = f"text: '{seg}'"
                            return best_label, best_source
                # If number found in segment but no keyword recognized, keep segment as source
                best_source = f"text: '{seg}'"

        # If not found in split segments, do a sliding window search across the full text
        for label, regex_list in cls.CONTEXT_PATTERNS.items():
            for reg in regex_list:
                match = re.search(rf'({reg}[^a-zA-Z0-9\n]{{0,20}}{num_pattern_str})', raw_text, re.IGNORECASE)
                if match:
                    best_label = label
                    best_source = f"text: '{match.group(0).strip()}'"
                    return best_label, best_source

        return best_label, best_source

    @classmethod
    def process_step3(cls, raw_text: str, normalized_amounts: List[float], step2_confidence: float = 0.82) -> Step3Response:
        """
        Executes Step 3: Classifies normalized amounts based on surrounding context.
        """
        classified_items: List[AmountItem] = []
        assigned_types = set()

        for val in normalized_amounts:
            label, _ = cls._find_provenance_and_label(raw_text, val)
            
            # Heuristic fallback if duplicate label or unrecognized
            if label == "other" or label in assigned_types:
                # Disambiguation logic based on standard accounting rules:
                # Usually max value is total_bill, if due and paid exist
                if "total_bill" not in assigned_types and val == max(normalized_amounts):
                    label = "total_bill"
                elif "paid" not in assigned_types:
                    label = "paid"
                elif "due" not in assigned_types:
                    label = "due"
                else:
                    label = "other"

            assigned_types.add(label)
            classified_items.append(AmountItem(type=label, value=val))

        # Enforce canonical ordering: total_bill -> paid -> due -> others
        order_map = {"total_bill": 1, "paid": 2, "due": 3, "discount": 4, "tax": 5, "other": 6}
        classified_items.sort(key=lambda x: order_map.get(x.type, 99))

        return Step3Response(
            amounts=classified_items,
            confidence=round(min(0.92, max(0.75, step2_confidence - 0.02)), 2)
        )

    @classmethod
    def process_step4(cls, currency: str, classified_amounts: List[AmountItem], raw_text: str) -> Step4Response:
        """
        Executes Step 4: Constructs the final standardized response with provenance audit trail
        and mathematical reconciliation guardrail.
        """
        final_amounts: List[FinalAmountItem] = []
        extracted_map: Dict[str, float] = {}

        for item in classified_amounts:
            _, source_str = cls._find_provenance_and_label(raw_text, item.value)
            
            # Clean up source string formatting to match expected format: text: 'Total: INR 1200'
            cleaned_source = source_str.replace("text: 'text: '", "text: '")
            
            final_amounts.append(
                FinalAmountItem(
                    type=item.type,
                    value=item.value,
                    source=cleaned_source
                )
            )
            extracted_map[item.type] = float(item.value)

        # Mathematical Guardrail: Total == Paid + Due
        reconciliation = None
        if "total_bill" in extracted_map and "paid" in extracted_map and "due" in extracted_map:
            total = extracted_map["total_bill"]
            paid = extracted_map["paid"]
            due = extracted_map["due"]
            discrepancy = round(total - (paid + due), 2)
            is_balanced = abs(discrepancy) < 0.01

            reconciliation = {
                "total_bill": total,
                "paid_plus_due": round(paid + due, 2),
                "is_balanced": is_balanced,
                "discrepancy": discrepancy,
                "status": "Verified (Total == Paid + Due)" if is_balanced else f"Discrepancy detected: {discrepancy}"
            }

        return Step4Response(
            currency=currency,
            amounts=final_amounts,
            status="ok",
            mathematical_reconciliation=reconciliation
        )
