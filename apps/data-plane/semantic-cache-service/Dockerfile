FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for numpy
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

EXPOSE 8088

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8088"]

