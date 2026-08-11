# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install -e ".[dev]"

COPY apps ./apps
COPY tests ./tests
COPY config ./config
COPY docs ./docs
COPY .env.example ./

RUN mkdir -p data/local data/raw data/processed data/external

EXPOSE 8501

CMD ["pytest"]
