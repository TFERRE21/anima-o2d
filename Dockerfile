# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

# Blender runs as its official bpy Python module; Mesa/Xvfb provide headless OpenGL
# for Eevee on CPU-only servers. The application and bpy use the same CPython ABI.
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb xauth libgl1 libegl1 libosmesa6 libx11-6 libxi6 libxrender1 \
    libxfixes3 libxkbcommon0 libsm6 libxext6 libxrandr2 libxinerama1 \
    libxcursor1 libxxf86vm1 libdbus-1-3 libfontconfig1 libfreetype6 \
    libwayland-client0 libwayland-egl1 libglib2.0-0 libstdc++6 libgomp1 \
    ffmpeg espeak-ng fonts-dejavu-core \
    && ldconfig \
    && ldconfig -p | grep -q 'libXfixes.so.3' \
    && python -c "import ctypes; ctypes.CDLL('libXfixes.so.3'); print('ANIMA_LIBXFIXES_OK')" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && python -c "import bpy; print('ANIMA_BLENDER_MODULE_OK', bpy.app.version_string)"

COPY backend ./backend
COPY web ./web

# Fail the image build if the 3D scene file cannot start under the deployed Python.
RUN test -s /app/backend/app/blender_scene.py \
    && python /app/backend/app/blender_scene.py --module --version-check

ENV PYTHONPATH=/app \
    ANIMA_STORAGE=/data/jobs \
    BLENDER_BACKEND=python-module \
    BLENDER_USER_CONFIG=/tmp/blender-config \
    PORT=5000

EXPOSE 5000
CMD ["sh","-c","uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-5000}"]
