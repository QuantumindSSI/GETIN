# ── Build Stage ──────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime Stage ────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 1001 getin && \
    useradd --system --uid 1001 --gid getin --create-home --shell /sbin/nologin getin

COPY --from=builder /install /usr/local

WORKDIR /app

COPY src/ src/
COPY config/ config/
COPY watchlist.yaml .

RUN mkdir -p /app/persist /app/logs /app/wallets && \
    chown -R getin:getin /app

# Wallets directory is empty in the image — generated at runtime.
# Private keys are mounted via docker secrets or environment variables.
# NEVER copy wallet files into the image.

USER getin:getin

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD pgrep -f "telegram_bot" > /dev/null || exit 1

CMD ["python", "-u", "-m", "src.telegram_bot"]