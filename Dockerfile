FROM node:20-slim AS fe
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-calc libreoffice-impress fonts-liberation fonts-dejavu \
    tesseract-ocr tesseract-ocr-por libpango-1.0-0 libpangoft2-1.0-0 && rm -rf /var/lib/apt/lists/*
RUN useradd -m app
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY --from=fe /backend/static ./static
RUN mkdir -p storage && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
