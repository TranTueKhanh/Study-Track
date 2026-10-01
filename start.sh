#!/bin/bash

# Khởi chạy màn hình ảo Xvfb
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99
sleep 2

# Khởi chạy Window Manager
fluxbox &
sleep 1

# Khởi chạy VNC Server
x11vnc -forever -nopw -shared -rfbport 5900 -display :99 &
sleep 1

# Khởi chạy Websockify Proxy (noVNC)
websockify --web=/usr/share/novnc 8080 localhost:5900 &
sleep 1

# Khởi chạy ứng dụng PyQt6
python main.py