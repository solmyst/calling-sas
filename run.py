import os
from pathlib import Path
from dotenv import load_dotenv
import uvicorn

load_dotenv(Path(__file__).parent / ".env", override=False)
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    if os.getenv("APP_ENV", "local") == "local" and host not in (
        "localhost",
        "127.0.0.1",
    ):
        raise SystemExit(
            "Local mode must bind to loopback. Configure hosted authentication before exposing the server."
        )
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=host,
        port=int(os.getenv("PORT", "8787")),
        access_log=False,
        log_level="info",
    )
