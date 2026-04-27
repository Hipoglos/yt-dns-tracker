FROM python:3.12-alpine

WORKDIR /app

# Only install what's needed
RUN apk add --no-cache gcc musl-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME ["/data"]
EXPOSE 8080

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
