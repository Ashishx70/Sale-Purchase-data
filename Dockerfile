FROM python:3.12-slim

# Create user with UID 1000 (Hugging Face Spaces runs as user 1000)
RUN useradd -m -u 1000 user

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    DATA_DIR=/app/data

# Set work directory
WORKDIR /app

# Install dependencies first (for caching layers)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=user:user . /app

# Create a local data folder as fallback, owned by user
RUN mkdir -p /app/data && chown -R user:user /app/data

# Switch to the non-root user
USER user

# Expose port 7860
EXPOSE 7860

# Run Gunicorn
CMD ["gunicorn", "app:app", "--config", "gunicorn.conf.py"]
