FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq for asyncpg runtime is not required (asyncpg bundles its own), but
# build-essential covers optional C extensions during install.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY portwiz_api ./portwiz_api
COPY migrations ./migrations
COPY alembic.ini entrypoint.sh ./

RUN pip install --upgrade pip \
    && pip install -e . \
    && chmod +x entrypoint.sh

# Run as an unprivileged user. The app needs no write access to the image and
# binds a non-privileged port (8000), so root is never required at runtime.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Release version, passed at build (e.g. --build-arg PORTWIZ_VERSION=0.19.0 from
# the git tag in CI). Read by the update check; empty falls back to __version__.
ARG PORTWIZ_VERSION=""
ENV PORTWIZ_VERSION=$PORTWIZ_VERSION

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["api"]
