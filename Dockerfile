FROM python:3.12-slim

# This is a genuinely large image because of LibreOffice 
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libreoffice \
    poppler-utils \
    pandoc \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend

# Run as a non-root user for defense in depth, since this container handles arbitrary user-uploaded files.
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# NOTE: keep --workers 1 while job state lives in an in-memory dict.
# Moving job state to Redis is the prerequisite for running multiple workers/replicas 
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]