FROM python:3.11-slim

# Install system dependencies: FFmpeg, Khmer Fonts, and Fontconfig
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-khmeros \
    fonts-dejavu-core \
    fontconfig \
    curl \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Ensure data directories exist and have open permissions
RUN mkdir -p data/uploads data/outputs data/voice_bank data/temp && chmod -R 777 /app

ENV PYTHONUNBUFFERED=1
ENV IS_CLOUD=true
ENV PORT=7860

EXPOSE 7860
EXPOSE 8000

# Start Uvicorn server with dynamic PORT support (default 7860 for Hugging Face Spaces)
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]

