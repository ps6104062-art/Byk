# UNIVERSE WA BOT

## Запуск

1. Установить зависимости:
```
pip install -r requirements.txt
```

2. Задать переменные окружения:
```
export BOT_TOKEN="ваш_токен_от_BotFather"
export ADMIN_IDS="123456789"  # TG ID главного админа (через запятую если несколько)
```

3. Запустить:
```
python main.py
```

## Структура

```
wabot/
├── main.py          # Точка входа, планировщик ворка
├── config.py        # Токен, ID админов, время работы
├── database.py      # Все операции с БД
├── keyboards.py     # Все клавиатуры
├── requirements.txt
└── handlers/
    ├── user.py      # Пользовательские команды
    └── admin.py     # Админка + вбив
```

## Роли
- `user` — обычный пользователь (сдаёт номера)
- `vbiv` — вбив (берёт номера из очереди)
- `admin` — полный доступ

## Деплой (VPS)
```bash
# Systemd сервис
sudo nano /etc/systemd/system/wabot.service

[Unit]
Description=WA Bot
After=network.target

[Service]
WorkingDirectory=/path/to/wabot
Environment=BOT_TOKEN=xxx
Environment=ADMIN_IDS=123456789
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target

sudo systemctl enable wabot
sudo systemctl start wabot
```
