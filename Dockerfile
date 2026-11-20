FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OLYMPICS_DB_PATH=/data/olympics.sqlite3
WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --system --gid 10001 olympics \
    && useradd --system --uid 10001 --gid 10001 olympics \
    && install -d -o 10001 -g 10001 -m 0700 /data

COPY manage.py .
COPY olympics/ olympics/

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=2).close()"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--forwarded-allow-ips=", "olympics.wsgi:application"]
