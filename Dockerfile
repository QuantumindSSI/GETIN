FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY watchlist.yaml .
COPY wallets/ wallets/

RUN useradd --create-home --shell /bin/bash getin && \
    chown -R getin:getin /app

USER getin

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "telegram_bot" || exit 1

CMD ["python", "-u", "-m", "src.telegram_bot"]