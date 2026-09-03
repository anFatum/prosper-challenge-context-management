FROM python:3.12-slim

# System deps required by aiortc (WebRTC transport used by the Pipecat bot).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libsrtp2-dev \
    libopus-dev \
    libvpx-dev \
    curl \
    # OpenCV runtime deps (pulled in by pipecat[webrtc] → cv2)
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .