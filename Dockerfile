FROM node:24-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend/src DOCUMIND_STORAGE=/app/storage DOCUMIND_FRONTEND=/app/frontend/dist OLLAMA_NO_CLOUD=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md alembic.ini requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ backend/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .
COPY --from=ui /ui/dist frontend/dist/
COPY data/ data/
COPY docs/ docs/
COPY scripts/ scripts/
COPY evaluation/ evaluation/
RUN useradd --create-home --uid 10001 documind && mkdir -p storage models && chown -R documind:documind /app
USER documind
EXPOSE 8765
CMD ["uvicorn", "documind_ai.api:app", "--host", "0.0.0.0", "--port", "8765", "--no-access-log"]
