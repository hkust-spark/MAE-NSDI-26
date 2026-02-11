#!/bin/bash
set -e
cp /usr/lib/libx264.a /usr/lib/x86_64-linux-gnu/.
git config --global --add safe.directory '*'
gclient sync
gn gen out/Default
ninja -C out/Default

sudo adduser --disabled-password --gecos "" mae 2>/dev/null || true
echo "mae:mae" | sudo chpasswd
sudo usermod -aG sudo mae
# Inside Docker: let mae write /workspace; restore original owner on exit so host edits keep working
if [ -f /.dockerenv ] && [ -d /workspace ]; then
  ORIG_OWNER=$(stat -c '%u:%g' /workspace)
  trap 'chown -R $ORIG_OWNER /workspace' EXIT
  chown -R mae:mae /workspace
fi
sudo ufw disable
sudo iptables -F
su - mae