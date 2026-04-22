FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    PIP_NO_CACHE_DIR=1 \
    YOLO_AUTOINSTALL=0 \
    ULTRALYTICS_AUTOINSTALL=0 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    git \
    curl \
    ca-certificates \
    tzdata && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    python -m pip install --upgrade pip setuptools wheel && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.lock.txt /tmp/requirements.lock.txt
RUN python -m pip install -r /tmp/requirements.lock.txt && \
    python -m pip check

COPY verify_env.py /workspace/verify_env.py

CMD ["bash", "-lc", "sleep infinity"]
