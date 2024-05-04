# Телеграм бот "Systema"

# Установка
Установщик [installer.bash](https://github.com/reques6e/TgBotSystemaLtd/blob/main/installer.bash)
В терминале: 
```
bash
┌──(reques6e㉿kali)-[~/Desktop/Project/TgBotCyxym]
└─$ chmod +x installer.bash
Установка завершена.
```
Работает под сервисом `tg_bot_systema.service`:
```
/etc/systemd/system/tg_bot_systema.service

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
ExecStart=$(which python) main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tg_bot_systema
systemctl start tg_bot_systema

echo "Установка завершена."

```

## Исходники:
API - [Docs](https://github.com/reques6e/SystemUtilis/blob/main/API.md) (API v1 для обычных пользователей)
