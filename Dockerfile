FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run sets $PORT; --workers 1 because test sessions live in memory
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
