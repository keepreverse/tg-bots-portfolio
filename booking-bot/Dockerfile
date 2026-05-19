FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data/seed_services.json ./data/seed_services.json

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["booking-bot"]
