"""Local-only synthetic microphone harness; never mounted by the product server."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(APP_ENV="local", DEMO_PASSWORD="", HOST="127.0.0.1",
                  PORT="8791", PUBLIC_ORIGIN="http://127.0.0.1:8791",
                  DATABASE_PATH=str(Path(__file__).resolve().parent.parent / "runtime/barge-in-validation.sqlite"))

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.main import create_app
import uvicorn

app = create_app()
root = Path(__file__).resolve().parent.parent
app.mount('/test-assets', StaticFiles(directory=root/'tests'), name='validation-assets')
app.add_api_route('/voice-validation', lambda: FileResponse(root/'tests/browser-voice.html'), methods=['GET'])

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8791, access_log=False)
