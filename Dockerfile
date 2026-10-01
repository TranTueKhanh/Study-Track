FROM python:3.10-slim

# Cài đặt các thư viện hệ thống (giữ nguyên gói cũ + thêm bộ libxcb cần thiết cho PyQt6)
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
    libxcb-cursor0 \
    libxcb-xinerama0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r scripts/requirements.txt

ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=xcb

EXPOSE 8080

RUN chmod +x start.sh

CMD ["./start.sh"]