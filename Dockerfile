FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    PORT=80

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m patchright install --with-deps chromium \
    && apt-get update \
    && apt-get install -y --no-install-recommends libarchive13 \
    && rm -rf /var/lib/apt/lists/*

COPY app.py subhd.py ./
COPY widgets ./widgets
COPY static ./static
EXPOSE 80
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-80} --proxy-headers --forwarded-allow-ips='*'"]
