FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    libgl1 \
    libglib2.0-0 \
    libqt5gui5 \
    libqt5widgets5 \
    libqt5core5a \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r scripts/requirements.txt

ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=xcb

EXPOSE 8080

RUN chmod +x start.sh

CMD ["./start.sh"]