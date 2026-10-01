#!/bin/bash

# Khởi chạy màn hình ảo
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Khởi chạy Window Manager
fluxbox &

# Khởi chạy VNC Server
x11vnc -forever -nopw -shared -rfbport 5900 -display :99 &

# Khởi chạy Websockify Proxy kết nối cổng 8080 tới VNC 5900
websockify --web=/usr/share/novnc 8080 localhost:5900 &

# Khởi chạy ứng dụng PyQt
python main.py