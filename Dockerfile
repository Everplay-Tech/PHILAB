FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -e "phi2_lab[platform]"

ENV PHILAB_DATABASE_URL=${PHILAB_DATABASE_URL}
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn phi2_lab.platform.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
