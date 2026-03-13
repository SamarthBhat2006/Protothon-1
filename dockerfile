# ─────────────────────────────────────────────────────────────
# Dockerfile — AI Meeting-to-Action System
# Uses Python 3.11 with deltalake (delta-rs). No Java required.
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/delta data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
