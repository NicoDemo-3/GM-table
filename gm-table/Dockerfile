FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN mkdir -p data

EXPOSE 5000
# threading async mode: simple and solid for a home-LAN game
CMD ["python", "-m", "app.server"]
