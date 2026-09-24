FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Данные (SQLite) живут на volume /data
ENV DB_PATH=/data/candidates.db

CMD ["python", "bot.py"]
