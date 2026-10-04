from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.api.routes import router as api_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
## MediExtract AI
### Intelligent Medical Bill & Receipt Financial Extractor

A production-grade pipeline designed to parse financial amounts, line items, and payment summaries from medical invoices and pharmacy receipts:
1. **Step 1 - OCR & Token Extraction**: Ingests typed text or noisy receipt images, extracting numeric tokens and inferring currency.
2. **Step 2 - Normalization**: Corrects OCR character/digit confusion matrix errors (`l` -> `1`, `O` -> `0`, etc.) and filters non-amounts.
3. **Step 3 - Classification by Context**: Contextually labels amounts into `total_bill`, `paid`, `due`, `discount`, and `tax`.
4. **Step 4 - Structured Output & Provenance**: Returns clean final JSON with audit source snippets and financial reconciliation guardrails.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Static Files for Demo UI
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
async def serve_home():
    """Serves the interactive web demo interface."""
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "MediExtract AI Service is active. Visit /docs for API documentation."}

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
