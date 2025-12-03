FROM python:3.11-slim

LABEL org.opencontainers.image.source=https://github.com/devopstales/imagepullsecret-patcher
LABEL org.opencontainers.image.description="Pull secret patcher"
LABEL org.opencontainers.image.licenses=Apache

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY imagepullsecret-patcher.py .
CMD ["python", "imagepullsecret-patcher.py"]
