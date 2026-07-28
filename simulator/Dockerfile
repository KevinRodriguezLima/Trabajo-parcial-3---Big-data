FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "run.py", "--scenario", "BASE", "--agents", "120", "--duration", "20", "--speed", "3600"]
