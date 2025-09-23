FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt || true
COPY src ./src
EXPOSE 8081
CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","8081"]
