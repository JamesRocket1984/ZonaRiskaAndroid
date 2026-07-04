#!/bin/bash
# ============================================================
#  Сборка APK для Android — «Зона Риска»
# ============================================================
#
#  ВАЖНО: Сборка APK работает ТОЛЬКО на Linux (Ubuntu/Debian).
#  На Windows используйте WSL2 (Ubuntu) или виртуальную машину.
#
#  Первый запуск займёт 30-60 минут (скачивание Android SDK/NDK).
#  Последующие сборки — 5-10 минут.
# ============================================================

set -e

echo "=== Сборка APK «Зона Риска» ==="

# Проверка ОС
if [[ "$(uname)" != "Linux" ]]; then
    echo "ОШИБКА: buildozer работает только на Linux."
    echo "На Windows используйте WSL2: https://learn.microsoft.com/windows/wsl/install"
    exit 1
fi

# Установка системных зависимостей (Ubuntu/Debian)
echo "--- Установка системных пакетов ---"
sudo apt update
sudo apt install -y python3-pip build-essential git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev

# Установка buildozer и Cython
echo "--- Установка buildozer ---"
pip3 install --upgrade buildozer Cython==0.29.36

# Сборка APK
echo "--- Запуск сборки (это долго при первом запуске!) ---"
buildozer -v android debug

echo ""
echo "============================================"
echo " ГОТОВО! APK лежит в папке bin/"
echo " Файл: bin/zonariska-1.0-*-debug.apk"
echo "============================================"
echo ""
echo "Установка на телефон:"
echo "  1. Скопируйте .apk на телефон"
echo "  2. Разрешите установку из неизвестных источников"
echo "  3. Откройте .apk и установите"
