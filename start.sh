#!/bin/bash

# 1. Tạo màn hình ảo Virtual Framebuffer (độ phân giải 1280x720)
Xvfb :99 -screen 0 1280x720x16 &
export DISPLAY=:99

# 2. Khởi chạy Window Manager nhẹ (Fluxbox)
fluxbox &

# 3. Khởi chạy VNC Server kết nối vào màn hình ảo
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 &

# 4. Chạy ứng dụng PyQt của bạn (Sửa main.py thành file chạy chính của bạn nếu cần)
python3 main.py &

# 5. Mở websockify / noVNC trên cổng được cấp bởi Render ($PORT)
websockify --web /usr/share/novnc $PORT localhost:5900