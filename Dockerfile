FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
ENV PORT=5000

EXPOSE 5000

CMD gunicorn --bind 0.0.0.0:$PORT app:app
