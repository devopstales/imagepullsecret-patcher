FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY serviceaccount_patcher.py .
CMD ["python", "serviceaccount_patcher.py"]
