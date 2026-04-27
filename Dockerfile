FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages: Postgres client lib, curl for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN useradd --create-home --shell /bin/bash --uid 1000 luma

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=luma:luma . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R luma:luma /app

USER luma

EXPOSE 8000

CMD ["gunicorn", "luma_support.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
