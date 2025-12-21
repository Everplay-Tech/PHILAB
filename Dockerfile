FROM python:3.10-slim

WORKDIR /app

COPY deploy/requirements-platform.txt /app/deploy/requirements-platform.txt
RUN pip install --no-cache-dir -r /app/deploy/requirements-platform.txt

COPY . /app

ENV PYTHONPATH=/app

ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn phi2_lab.platform.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
