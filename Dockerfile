FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

VOLUME ["/data"]

RUN mkdir -p /data && chown -R app:app /app /data

USER app

CMD ["cliproxyapi-usage-persist"]
