#!/bin/bash
# ==============================================================
# SVA Clone Dubbing - 1-Click Ubuntu / Debian VPS Setup Script
# ==============================================================

set -e

echo "🚀 Starting SVA Clone Dubbing Server Installation..."

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python, FFmpeg, and Khmer Fonts
sudo apt install -y python3 python3-pip python3-venv ffmpeg fonts-khmeros fonts-dejavu-core fontconfig curl git

# Rebuild font cache
sudo fc-cache -f -v

APP_DIR=$(pwd)
echo "📂 Working directory: $APP_DIR"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Install python dependencies
echo "📥 Installing Python requirements..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Ensure data directories exist
mkdir -p data/uploads data/outputs data/voice_bank data/temp

# Create systemd background service
echo "⚙️ Creating 24/7 systemd service (sva-dubbing)..."
SERVICE_FILE="/etc/systemd/system/sva-dubbing.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=SVA Clone Dubbing Web Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python server.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=PORT=8000
Environment=IS_CLOUD=true

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable service
sudo systemctl daemon-reload
sudo systemctl enable sva-dubbing
sudo systemctl restart sva-dubbing

SERVER_IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')

echo "=============================================================="
echo "✅ SUCCESS! SVA Clone Dubbing is now running 24/7 in cloud!"
echo ""
echo "🌐 Access your app from ANY phone, iPad, or computer:"
echo "👉 http://${SERVER_IP}:8000"
echo ""
echo "Commands to manage your server:"
echo "- Check status : sudo systemctl status sva-dubbing"
echo "- Restart      : sudo systemctl restart sva-dubbing"
echo "- View logs    : sudo journalctl -u sva-dubbing -f"
echo "=============================================================="
