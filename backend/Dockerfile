FROM python:3.11-slim
WORKDIR /app

# Cache bust v16 - checked_items progress endpoint
RUN echo "build-v16"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
