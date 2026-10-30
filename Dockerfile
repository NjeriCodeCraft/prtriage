FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY samples ./samples

# Secrets (GEMINI_API_KEY etc.) are provided as environment variables by the host, never baked into the image.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
