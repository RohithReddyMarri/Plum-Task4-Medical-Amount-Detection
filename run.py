import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.PROJECT_NAME} on http://localhost:{settings.PORT}")
    print(f"Swagger API Docs: http://localhost:{settings.PORT}/docs")
    print(f"Interactive Web Demo: http://localhost:{settings.PORT}/")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
