# Stage 1: Build the Vue frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/ .

RUN cd partner-components && npm install && npm run build && rm -rf node_modules

RUN npm ci

ENV VITE_API_URL=""
RUN npm run build


# Stage 2: Python backend + frontend dist
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY backend/download_models.py .
COPY backend/start.sh .

COPY --from=frontend-build /app/frontend/dist /app/static

ENV STATIC_DIR=/app/static
ENV MODEL_DIR=/home/models
ENV DATABASE_PATH=/home/data/buildingstock.db

EXPOSE 8001

CMD ["sh", "start.sh"]
