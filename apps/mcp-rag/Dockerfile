FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
COPY contracts ./contracts
EXPOSE 8765
CMD ["python", "src/server.py"]

