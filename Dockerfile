FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt requirements-workers.txt ./
RUN pip install --no-cache-dir -r requirements-workers.txt gunicorn==23.0.0 psycopg2-binary==2.9.10
COPY . .

RUN useradd --create-home --shell /bin/sh appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app
COPY docker/entrypoint.sh /usr/local/bin/article-studio-entrypoint
RUN chmod +x /usr/local/bin/article-studio-entrypoint
USER appuser

EXPOSE 8000
ENTRYPOINT ["article-studio-entrypoint"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
