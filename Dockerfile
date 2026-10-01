# syntax=docker/dockerfile:1

FROM python:3.11-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG INSTALL_APT_PACKAGES=""
RUN if [ -n "$INSTALL_APT_PACKAGES" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends $INSTALL_APT_PACKAGES && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY pyproject.toml README.md requirements.lock ./
RUN python -m pip install --require-hashes -r requirements.lock

COPY src ./src
ARG INSTALL_EXTRAS=""
RUN if [ -n "$INSTALL_EXTRAS" ]; then \
      python -m pip install -e ".[$INSTALL_EXTRAS]"; \
    else \
      python -m pip install --no-deps -e .; \
    fi

COPY apps ./apps
COPY tests ./tests
COPY config ./config
COPY docs ./docs
COPY db ./db
COPY .env.example ./

RUN mkdir -p data/local data/raw data/processed data/external

EXPOSE 8501

CMD ["pytest"]
