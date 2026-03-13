FROM python:3.11-slim
WORKDIR /app

# Cache bust v11 - OpenAI GPT-4o-mini PDF parser
RUN echo "build-v11"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
