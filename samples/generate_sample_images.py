from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random

SAMPLES_DIR = Path(__file__).resolve().parent

def create_receipt_image(text_lines, filename, add_noise=False, heavy_noise=False):
    width, height = 500, 300
    img = Image.new("RGB", (width, height), color=(250, 250, 245))
    draw = ImageDraw.Draw(img)

    # Use default PIL font or fallback
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    y_offset = 40
    for line in text_lines:
        draw.text((40, y_offset), line, fill=(20, 20, 20), font=font)
        y_offset += 35

    if add_noise:
        # Add slight artifacts / dots
        for _ in range(500):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            draw.point((x, y), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))
        img = img.filter(ImageFilter.SMOOTH_MORE)

    if heavy_noise:
        # Completely obscure / blur
        for _ in range(3000):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            draw.point((x, y), fill=(random.randint(0, 50), random.randint(0, 50), random.randint(0, 50)))
        img = img.filter(ImageFilter.GaussianBlur(radius=8))

    output_path = SAMPLES_DIR / filename
    img.save(output_path)
    print(f"Generated sample image: {output_path}")

if __name__ == "__main__":
    # Sample 1: Standard clean receipt
    create_receipt_image(
        [
            "PLUM HEALTHCARE CLINIC",
            "-------------------------",
            "Consultation & Diagnostic",
            "Total: INR 1200",
            "Paid: 1000",
            "Due: 200",
            "Discount: 10%"
        ],
        "sample_receipt_standard.png"
    )

    # Sample 2: Noisy OCR receipt with digit artifacts
    create_receipt_image(
        [
            "PLUM MEDICAL CENTER",
            "-------------------------",
            "T0tal: Rs l200",
            "Pald: 1000",
            "Due: 200"
        ],
        "sample_receipt_noisy.png",
        add_noise=True
    )

    # Sample 3: Degraded unreadable receipt (guardrail trigger)
    create_receipt_image(
        [
            "### UNREADABLE ###",
            "~~~ ????? ~~~"
        ],
        "sample_receipt_unreadable.png",
        heavy_noise=True
    )
