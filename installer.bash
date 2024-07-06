#!/bin/bash

install_dialog() {
  if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y dialog
  elif command -v yum &> /dev/null; then
    sudo yum install -y dialog
  elif command -v dnf &> /dev/null; then
    sudo dnf install -y dialog
  elif command -v zypper &> /dev/null; then
    sudo zypper install -y dialog
  else
    echo "Не удалось определить пакетный менеджер. Установите 'dialog' вручную."
    exit 1
  fi
}

if ! command -v dialog &> /dev/null; then
  echo "Утилита 'dialog' не найдена. Установка..."
  install_dialog
fi

if [[ ! -f "LICENSE" ]]; then
  echo "Файл LICENSE не найден!"
  exit 1
fi

dialog --title "Лицензионное соглашение" --textbox LICENSE 20 60

dialog --yesno "Согласны ли вы с условиями лицензии?" 10 60
response=$?

if [ $response -ne 0 ]; then
  dialog --msgbox "Вы не согласились с условиями лицензии." 10 60
  clear
  exit 0
fi

service_name=$(dialog --inputbox "Введите название сервиса (или введите 'default' для использования стандартного 'tg_bot_systema'):" 10 60 3>&1 1>&2 2>&3)

if [ $? -ne 0 ]; then
  dialog --msgbox "Вы отменили установку." 10 60
  clear
  exit 0
fi

if [ "$service_name" == "default" ]; then
  service_name="tg_bot_systema"
fi

clear

chmod +x main.py
sudo apt install -y python3-pip
pip3 install -r assets/requirements.txt

cat > /etc/systemd/system/${service_name}.service <<EOF
[Unit]
Description=TgBotSystema By Reques6e
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${service_name}
sudo systemctl start ${service_name}

dialog --msgbox "Установка завершена." 10 60
clear
