FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MP_STATIC_DIR=/app/frontend/dist
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY musicpilot ./musicpilot
RUN pip install --no-cache-dir .
COPY --from=frontend /app/frontend/dist /app/frontend/dist
EXPOSE 8000
CMD ["uvicorn", "musicpilot.infra.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
