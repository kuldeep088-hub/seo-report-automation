FROM python:3.11-slim

WORKDIR /app

# System libraries needed by matplotlib and cairo
RUN apt-get update && apt-get install -y \
    gcc \
    libfreetype6-dev \
    pkg-config \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

CMD ["sh", "-c", "python startup.py && python scheduler.py"]
