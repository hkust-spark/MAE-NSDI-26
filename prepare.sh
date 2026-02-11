#!/bin/bash
cp /usr/lib/libx264.a /usr/lib/x86_64-linux-gnu/.
sudo adduser mae
sudo usermod -aG sudo mae
sudo ufw disable
su - mae
sudo iptables -F
cd /workspace/my_experiment/code/
#./run.sh -i Lecture -p send_and_recv