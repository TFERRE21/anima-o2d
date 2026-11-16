FROM python:3.12-slim

# Anima Studio 2D — native CPU drawing with narration. No Blender/Xvfb/GPU.
RUN apt-get update && apt-get install -y --no-install-recommends     ffmpeg espeak-ng fonts-dejavu-core ca-certificates     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY web ./web
COPY docs ./docs

ENV PYTHONPATH=/app     ANIMA_STORAGE=/data/jobs     ANIMA_RENDER_ENGINE=2d     ANIMA_DRAW_FPS=8     ANIMA_AUTO_INSTALL_BLENDER=0     PORT=5000

RUN mkdir -p /data/jobs &&     python -c "from PIL import Image; import fastapi, edge_tts; print('ANIMA_2D_CPU_READY')"

EXPOSE 5000
CMD ["sh","-c","uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-5000}"]
