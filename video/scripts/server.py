"""Only the recording workspace. Never mounts production data or changes app code."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.update(APP_ENV='local',DEMO_PASSWORD='',HOST='127.0.0.1',PORT='8792',PUBLIC_ORIGIN='http://127.0.0.1:8792',DATABASE_PATH=str(ROOT/'runtime/hackathon-video.sqlite'))
from fastapi.staticfiles import StaticFiles
from app.main import create_app
import uvicorn
app=create_app()
app.mount('/video-audio',StaticFiles(directory=ROOT/'video/public/audio'),name='video-audio')
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8792,access_log=False,log_level='warning')
