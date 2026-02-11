#!/bin/bash
cp /usr/lib/libx264.a /usr/lib/x86_64-linux-gnu/.
sudo adduser --disabled-password --gecos "" mae 2>/dev/null || true
echo "mae:mae" | sudo chpasswd
sudo usermod -aG sudo mae
sudo ufw disable
su - mae
sudo iptables -F
gclient sync
gn gen out/Default
ninja -C out/Default
cd /workspace/my_experiment/data
ffmpeg -i Lecture.mp4 Lecture.yuv
cd /workspace/my_experiment/code/