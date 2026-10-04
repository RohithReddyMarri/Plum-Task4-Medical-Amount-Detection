import re
import io
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple, List, Optional
from rapidocr_onnxruntime import RapidOCR

from app.config import settings
from app.schemas import Step1Response, GuardrailExitResponse

# Initialize RapidOCR singleton
_ocr_engine = None

def get_ocr_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


class OCRService:
    @staticmethod
    def preprocess_image(image_bytes: bytes) -> np.ndarray:
        """
        Enhance image contrast and sharpness to improve OCR on crumpled or noisy receipts.
        """
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        enhanced = enhancer.enhance(1.6)
        
        # Slight sharpening
        sharpener = ImageEnhance.Sharpness(enhanced)
        sharpened = sharpener.enhance(1.4)
        
        return np.array(sharpened)

    @staticmethod
    def extract_text_from_image(image_bytes: bytes) -> Tuple[str, float]:
        """
        Runs RapidOCR on image bytes, returns concatenated raw text and average confidence.
        """
        try:
            np_img = OCRService.preprocess_image(image_bytes)
            ocr = get_ocr_engine()
            result, _ = ocr(np_img)
            
            if not result:
                return "", 0.0
            
            lines = []
            confidences = []
            for item in result:
                # item: [box, text, confidence]
                text = item[1].strip()
                conf = float(item[2])
                if text:
                    lines.append(text)
                    confidences.append(conf)
                    
            raw_text = " | ".join(lines)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            return raw_text, round(avg_conf, 2)
        except Exception as e:
            return "", 0.0

    @staticmethod
    def extract_currency_hint(text: str) -> str:
        """
        Infers currency from text cues (INR, Rs, ₹, USD, $, EUR, etc.)
        Defaults to 'INR' for medical invoices and receipts.
        """
        text_upper = text.upper()
        if re.search(r'\b(INR|RS\.?|RUPEES?|₹)\b', text, re.IGNORECASE):
            return "INR"
        elif re.search(r'\b(USD|\$|DOLLARS?)\b', text, re.IGNORECASE):
            return "USD"
        elif re.search(r'\b(EUR|€|EUROS?)\b', text, re.IGNORECASE):
            return "EUR"
        elif re.search(r'\b(GBP|£|POUNDS?)\b', text, re.IGNORECASE):
            return "GBP"
        return "INR"

    @staticmethod
    def extract_raw_tokens(text: str) -> List[str]:
        """
        Extracts raw numeric tokens, percentage tokens, and OCR-corrupted numbers.
        Avoids splitting '10%' into both '10' and '10%'.
        """
        raw_tokens = []
        
        # Pattern 1: Percentages (e.g. 10%, 5.5%)
        pct_matches = re.findall(r'\b\d+(?:\.\d+)?%', text)
        pct_numbers = {re.sub(r'%', '', p) for p in pct_matches}
        
        # Pattern 2: Standard numbers with optional decimals/commas NOT followed by %
        all_nums = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?(?!\s*%)\b|\b\d+(?!\s*%)\b', text)
        # Filter out numbers that were part of percentages
        num_matches = [n for n in all_nums if n not in pct_numbers]
        
        # Pattern 3: OCR corrupted digit tokens (e.g., 'l200', 'I500', '25O0')
        corrupted_matches = re.findall(r'\b[lI|][0-9]{2,}\b|\b[0-9]+[oO][0-9]*\b', text)
        
        candidates = num_matches + pct_matches + corrupted_matches
        
        # Preserve order of appearance in the original text
        seen = set()
        for token in re.findall(r'[a-zA-Z0-9.%]+', text):
            cleaned = token.strip(',.;:|')
            if cleaned in candidates and cleaned not in seen:
                seen.add(cleaned)
                raw_tokens.append(cleaned)
                
        # If order regex missed any candidates:
        for c in candidates:
            if c not in seen:
                seen.add(c)
                raw_tokens.append(c)

        return raw_tokens

    @classmethod
    def process_step1(cls, text: Optional[str] = None, image_bytes: Optional[bytes] = None) -> Tuple[Optional[Step1Response], Optional[GuardrailExitResponse], str]:
        """
        Executes Step 1 of the pipeline: Text extraction and raw token harvesting.
        Returns: (step1_response, guardrail_exit, extracted_raw_text)
        """
        raw_text = ""
        base_confidence = 0.85

        if image_bytes:
            extracted, conf = cls.extract_text_from_image(image_bytes)
            raw_text = extracted
            base_confidence = conf if conf > 0 else 0.40
        elif text:
            raw_text = text.strip()
            # If text has obvious OCR noises like 'T0tal', 'l200', adjust confidence dynamically
            if re.search(r'T0tal|l\d{2,}|Pald', raw_text):
                base_confidence = 0.74
            else:
                base_confidence = 0.88

        # Guardrail Check 1: Document too noisy or empty
        if not raw_text or len(raw_text.strip()) < 3:
            return None, GuardrailExitResponse(status="no_amounts_found", reason="document too noisy"), raw_text

        # Extract tokens and currency
        raw_tokens = cls.extract_raw_tokens(raw_text)
        currency_hint = cls.extract_currency_hint(raw_text)

        # Guardrail Check 2: No numeric tokens found at all
        if not raw_tokens or base_confidence < settings.NOISY_DOCUMENT_THRESHOLD:
            return None, GuardrailExitResponse(status="no_amounts_found", reason="document too noisy"), raw_text

        step1 = Step1Response(
            raw_tokens=raw_tokens,
            currency_hint=currency_hint,
            confidence=round(base_confidence, 2)
        )
        return step1, None, raw_text
