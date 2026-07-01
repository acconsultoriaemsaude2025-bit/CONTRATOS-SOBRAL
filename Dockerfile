FROM python:3.11-slim

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel Cython
RUN pip install numpy==1.26.4
RUN pip install -r requirements.txt

COPY . .

CMD gunicorn --chdir app app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
