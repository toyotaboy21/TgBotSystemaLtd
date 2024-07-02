#!/bin/bash

# Функция для установки dialog
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

# Проверка наличия dialog, установка при необходимости
if ! command -v dialog &> /dev/null; then
  echo "Утилита 'dialog' не найдена. Установка..."
  install_dialog
fi

# Проверка наличия файла LICENSE
if [[ ! -f "LICENSE" ]]; then
  echo "Файл LICENSE не найден!"
  exit 1
fi

# Вывод содержимого файла LICENSE
dialog --title "Лицензионное соглашение" --textbox LICENSE 20 60

# Спрашиваем согласие
dialog --yesno "Согласны ли вы с условиями лицензии?" 10 60
response=$?

# Проверка ответа пользователя
if [ $response -ne 0 ]; then
  dialog --msgbox "Вы не согласились с условиями лицензии." 10 60
  clear
  exit 0
fi

# Запрашиваем название сервиса
service_name=$(dialog --inputbox "Введите название сервиса (или введите 'default' для использования стандартного 'tg_bot_systema'):" 10 60 3>&1 1>&2 2>&3)

# Проверка нажатия кнопки Cancel
if [ $? -ne 0 ]; then
  dialog --msgbox "Вы отменили установку." 10 60
  clear
  exit 0
fi

# Устанавливаем значение по умолчанию, если введено 'default'
if [ "$service_name" == "default" ]; then
  service_name="tg_bot_systema"
fi

clear

# Основные команды установки
chmod +x main.py
sudo apt install -y python3-pip
pip3 install -r assets/requirements.txt

# Создание service файла
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

# Перезагрузка systemd и запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable ${service_name}
sudo systemctl start ${service_name}

# Уведомление об успешной установке
dialog --msgbox "Установка завершена." 10 60
clear
