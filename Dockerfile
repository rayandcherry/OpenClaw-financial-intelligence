FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY src/ src/
COPY alembic.ini .
COPY src/bot/db/migrations/ src/bot/db/migrations/

EXPOSE 8080

CMD ["python", "src/bot.py"]
