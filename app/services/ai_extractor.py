import json
import logging
from typing import Optional, Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)

class AIExtractorService:
    """
    Leverages Gemini Multimodal / LLM capabilities for chaining, semantic disambiguation,
    and validation when GEMINI_API_KEY is configured in the environment.
    """

    @classmethod
    def is_ai_available(cls) -> bool:
        return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    @classmethod
    def extract_with_gemini(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini to extract financial fields and context labels from ambiguous bill text.
        """
        if not cls.is_ai_available():
            return None

        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            prompt = f"""
            You are an expert medical billing AI for an insurance platform.
            Analyze the following medical bill/receipt text:
            \"\"\"{text}\"\"\"

            Extract the financial amounts and their exact context.
            Adhere strictly to these rules:
            1. Normalize OCR mistakes (e.g. 'l200' -> 1200, 'T0tal' -> Total).
            2. Ignore percentage rates (like discount % or tax %) as amounts.
            3. Classify each amount into: 'total_bill', 'paid', 'due', 'discount', or 'tax'.
            4. Provide the exact source text snippet as provenance.
            5. Determine the currency (e.g., INR, USD).

            Respond with pure JSON conforming to this schema:
            {{
              "currency": "INR",
              "amounts": [
                {{"type": "total_bill", "value": 1200, "source": "text: 'Total: INR 1200'"}},
                {{"type": "paid", "value": 1000, "source": "text: 'Paid: 1000'"}},
                {{"type": "due", "value": 200, "source": "text: 'Due: 200'"}}
              ]
            }}
            """

            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json"
                }
            )

            if response and response.text:
                data = json.loads(response.text)
                return data
        except Exception as e:
            logger.warning(f"Gemini AI extraction fallback triggered: {e}")
            return None

        return None
