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
# When host is Linux: let mae write /workspace in container; restore owner on exit so host edits keep working.
# Skip when host is macOS (pass -e HOST_IS_LINUX=1 only on Linux; see README).
if [ -f /.dockerenv ] && [ -d /workspace ] && [ "${HOST_IS_LINUX}" = "1" ]; then
  ORIG_OWNER=$(stat -c '%u:%g' /workspace)
  trap 'chown -R $ORIG_OWNER /workspace' EXIT
  chown -R mae:mae /workspace
fi
sudo ufw disable
sudo iptables -F
su - mae