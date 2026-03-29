FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y \
    libpq-dev \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# deps
COPY requirements.txt .
RUN pip install --upgrade wheel
RUN pip install --upgrade setuptools
RUN pip install --upgrade pip && pip install -r requirements.txt

# app
COPY . /app

EXPOSE 8080

CMD ["sh", "-c", "gunicorn main:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker"]