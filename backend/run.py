import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=9050,
        reload=True,
        log_level="info"
    )