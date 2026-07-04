[app]

# Название приложения
title = Зона Риска

# Имя пакета
package.name = zonariska
package.domain = com.zonariska.game

# Исходники
source.dir = .
source.include_exts = py,png,jpg,mp3,wav,ico,ttf

# Версия
version = 1.0

# Требования (pygame для android идёт через SDL2)
requirements = python3,pygame

# Ориентация экрана — вертикальная (игра вертикальная)
orientation = portrait

# Иконка приложения
icon.filename = %(source.dir)s/assets/icon.png

# Заставка (splash) — можно ту же иконку
presplash.filename = %(source.dir)s/assets/icon.png

# Полноэкранный режим
fullscreen = 1

[buildozer]

# Уровень логирования (2 = подробно)
log_level = 2

# Предупреждать при запуске от root
warn_on_root = 1

[app:android]

# Разрешения Android
android.permissions = INTERNET

# API уровни
android.api = 33
android.minapi = 21
android.ndk = 25b

# Архитектуры (arm64 для современных устройств + armeabi для старых)
android.archs = arm64-v8a, armeabi-v7a

# Принять лицензии SDK автоматически
android.accept_sdk_license = True

# Не требовать резервного копирования
android.allow_backup = True
