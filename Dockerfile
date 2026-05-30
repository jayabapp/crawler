FROM python:3.11-slim-bookworm

WORKDIR /app

RUN printf '%s\n' \
    'deb https://mirror.aminidc.com/debian bookworm main contrib non-free non-free-firmware' \
    'deb https://mirror.aminidc.com/debian bookworm-updates main contrib non-free non-free-firmware' \
    > /etc/apt/sources.list && \
    rm -f /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY wheels /wheels

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium

COPY . .


CMD ["python3", "main.py", "rentTemporary"]