# Build context: the repo root (see deploy/docker-compose.yml).

FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    APP_ENV=production
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home app \
    && python -m venv /opt/venv \
    && chown -R app:app /opt/venv
USER app
WORKDIR /app/backend
COPY --chown=app:app backend/pyproject.toml ./
COPY --chown=app:app backend/app ./app
# Install the dependencies, then drop the package itself: the source in /app/backend runs.
RUN pip install --no-cache-dir . && pip uninstall -y schedler
COPY --chown=app:app backend/alembic.ini ./
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app --from=web /web/dist /app/frontend/dist
COPY --chown=app:app deploy/entrypoint.sh /app/entrypoint.sh
EXPOSE 8000
CMD ["/app/entrypoint.sh"]
