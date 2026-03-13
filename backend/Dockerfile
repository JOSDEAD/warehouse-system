FROM python:3.11-slim
WORKDIR /app

# Cache bust: fuerza rebuild completo en cada deploy
ARG CACHE_BUST=1
RUN echo "Cache bust: $CACHE_BUST"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
