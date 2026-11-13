FROM python:3.12-slim

# Runtime de produção Cartoon 3D: Blender em modo background + Eevee + Xvfb.
RUN apt-get update && apt-get install -y --no-install-recommends \
    blender xvfb xauth ffmpeg espeak-ng fonts-dejavu-core ca-certificates \
    libgl1 libegl1 libx11-6 libxi6 libxrender1 libxfixes3 libxkbcommon0 \
    libsm6 libxext6 libxrandr2 libxinerama1 libxcursor1 libxxf86vm1 \
    libdbus-1-3 libfontconfig1 libfreetype6 libwayland-client0 \
    libwayland-egl1 libglib2.0-0 libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY web ./web
COPY docs ./docs

ENV PYTHONPATH=/app \
    ANIMA_STORAGE=/data/jobs \
    ANIMA_RENDER_ENGINE=3d \
    ANIMA_BLENDER_THREADS=6 \
    ANIMA_EEVEE_SAMPLES=4 \
    ANIMA_RENDER_SCALE=75 \
    PORT=5000

RUN mkdir -p /data/jobs && \
    xvfb-run -a blender --background --factory-startup --python-expr "import bpy; print('ANIMA_BLENDER_READY=' + bpy.app.version_string)" && \
    python -c "from PIL import Image; import fastapi, edge_tts; print('ANIMA_CARTOON_3D_RUNTIME_READY')"

EXPOSE 5000
CMD ["sh","-c","uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-5000}"]
