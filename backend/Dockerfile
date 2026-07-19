FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app

# nodes.config.json lives at the repo root and is mounted/copied in by
# docker-compose (build context = repo root). See docker-compose.yml.
ENV NODES_CONFIG_PATH=/config/nodes.config.json

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
