FROM python:3.10-slim

# Cài đặt các thư viện hệ thống cần thiết cho PyQt, màn hình ảo Xvfb và noVNC
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    websockify \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libqt5gui5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy toàn bộ file trong folder dự án vào container
COPY . /app

# Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Cấp quyền thực thi cho file start.sh
RUN chmod +x /app/start.sh

# Chạy script khởi động khi Container bật
CMD ["/app/start.sh"]