# ── Stage 1: build ─────────────────────────────────────────────────────────
# Compile C-extension wheels (aiortc, av, etc.) that need dev headers.
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libsrtp2-dev \
    libopus-dev \
    libvpx-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────────────────────
# Only runtime shared libraries — no compilers or headers.
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security.
RUN addgroup --system --gid 1001 app \
 && adduser  --system --uid 1001 --ingroup app --no-create-home app

# Copy compiled packages from the builder stage.
COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=app:app . .

USER app