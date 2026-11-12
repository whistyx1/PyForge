FROM python:3.13-slim-bookworm

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
RUN python app/manage.py collectstatic --noinput

RUN useradd -m appuser
RUN mkdir -p /data && chown appuser:appuser /data
USER appuser

WORKDIR /app/app
ENV DJANGO_DEBUG=false DJANGO_DB_PATH=/data/db.sqlite3

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=5 CMD ["python", "/app/app/healthcheck.py"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
