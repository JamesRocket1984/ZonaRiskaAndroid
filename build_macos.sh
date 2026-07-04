#!/bin/bash
# === Сборка ЗОНА РИСКА для macOS (.app) ===
set -e
echo "=== ЗОНА РИСКА — сборка под macOS ==="

if ! command -v python3 &>/dev/null; then
  echo "[!] Python 3 не найден. Установи: brew install python  (или с python.org)"
  exit 1
fi

echo "Создаю виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

echo "Устанавливаю зависимости..."
pip install --quiet --upgrade pip
pip install --quiet pygame pyinstaller

echo "Собираю .app (1-3 минуты)..."
pyinstaller --onefile --windowed --name "ZonaRiska" \
  --add-data "core.py:." --add-data "entities.py:." main.py

echo ""
echo "============================================"
echo " Готово: dist/ZonaRiska.app  и  dist/ZonaRiska"
echo ""
echo " Если macOS блокирует запуск ('неизвестный разработчик'):"
echo "   правый клик по .app -> Открыть -> Открыть,"
echo "   либо: xattr -cr dist/ZonaRiska.app"
echo "============================================"
