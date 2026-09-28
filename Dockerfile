FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine ./engine
COPY api ./api
COPY worker ./worker
COPY alembic ./alembic
COPY alembic.ini .
EXPOSE 8000
CMD ["uvicorn", "--factory", "api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
