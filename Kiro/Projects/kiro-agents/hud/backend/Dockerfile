FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r -u 1000 darius && chown -R darius /app
USER darius
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
