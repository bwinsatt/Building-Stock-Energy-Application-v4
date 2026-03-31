FROM python:3.11-slim

WORKDIR /app

# Install system packages required by numpy/pandas/scikit-learn/xgboost
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY download_models.py .
COPY start.sh .

EXPOSE 8001

CMD ["sh", "start.sh"]
