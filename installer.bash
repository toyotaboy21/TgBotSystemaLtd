#!/bin/bash

chmod +x main.py
sudo apt install python3-pip
pip3 install -r assets/requirements.txt

cat > /etc/systemd/system/tg_bot_systema.service <<EOF
[Unit]
Description=Flask App
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tg_bot_systema
systemctl start tg_bot_systema

echo "Установка завершена."
