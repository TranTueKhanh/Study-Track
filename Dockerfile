FROM python:3.10-slim

# Cài đặt các thư viện hệ thống cần thiết cho PyQt, màn hình ảo Xvfb và noVNC
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    libgl1 \
    libglib2.0-0 \
    libqt5gui5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r scripts/requirements.txt

EXPOSE 8080

RUN chmod +x start.sh

CMD ["./start.sh"]