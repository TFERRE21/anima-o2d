FROM python:3.12-slim

# Blender runs headlessly through Xvfb + Mesa software OpenGL in CPU-only VPS containers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    blender xvfb xauth libgl1-mesa-dri libegl1 libosmesa6 \
    ffmpeg espeak-ng fonts-dejavu-core \
    && test -x /usr/bin/blender \
    && /usr/bin/blender --background --factory-startup --python-expr \
       "import bpy; print('ANIMA_BLENDER_IMAGE_OK', bpy.app.version_string)" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY web ./web

# Fail the image build if either the real Blender engine or its Python scene file is missing.
RUN test -s /app/backend/app/blender_scene.py \
    && /usr/bin/blender --background --factory-startup --python-exit-code 1 \
       --python /app/backend/app/blender_scene.py -- --version-check

ENV PYTHONPATH=/app \
    ANIMA_STORAGE=/data/jobs \
    ANIMA_RENDER_ENGINE=blender \
    BLENDER_BIN=/usr/bin/blender \
    BLENDER_USER_CONFIG=/tmp/blender-config \
    PORT=5000

EXPOSE 5000
CMD ["sh","-c","uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-5000}"]
