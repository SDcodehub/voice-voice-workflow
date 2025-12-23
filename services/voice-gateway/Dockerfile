FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
# We would assume protos are compiled or copied here. 
# For now, let's keep it simple.

CMD ["python", "src/main.py"]

