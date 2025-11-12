# Dockerfile for nwpio

FROM python:3.11-slim

# Install system dependencies for GRIB support
RUN apt-get update && apt-get install -y \
    libeccodes-dev \
    libeccodes-tools \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY nwpio/ ./nwpio/
COPY pyproject.toml .
COPY README.md .

# Install the package
RUN pip install --no-cache-dir -e .

# # Create non-root user
# RUN useradd -m -u 1000 nwpuser && chown -R nwpuser:nwpuser /app
# USER nwpuser

# Set entrypoint
ENTRYPOINT ["nwpio"]
CMD ["--help"]
