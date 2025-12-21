FROM python:3.10-slim

WORKDIR /app

COPY deploy/requirements-platform.txt /app/deploy/requirements-platform.txt
RUN pip install --no-cache-dir -r /app/deploy/requirements-platform.txt

COPY . /app

ENV PYTHONPATH=/app

ENV PORT=8080

EXPOSE 8080

RUN chmod +x /app/deploy/start_api.sh
CMD ["/app/deploy/start_api.sh"]
