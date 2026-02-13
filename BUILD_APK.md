# Сборка APK (Order Manager)

Buildozer работает только в **Linux**. На Windows используйте один из способов ниже.

## 1. GitHub Actions (без установки Linux)

Если проект в GitHub — APK можно собрать в облаке и скачать.

1. Создайте репозиторий на GitHub и загрузите проект (или откройте его в GitHub).
2. Откройте вкладку **Actions** → workflow **Build APK** → **Run workflow** → **Run workflow**.
3. Дождитесь окончания сборки (первый раз может занять 30–50 минут: скачиваются SDK и NDK).
4. В завершённом запуске нажмите **ordermanager-apk** в блоке Artifacts и скачайте архив с APK.

При каждом пуше в ветку `main`/`master` сборка запускается автоматически.

## 2. WSL2 (сборка на своём ПК)

1. Установите [WSL2](https://docs.microsoft.com/ru-ru/windows/wsl/install) и дистрибутив Ubuntu.
2. В WSL откройте папку проекта:
   ```bash
   cd /mnt/c/order-app
   ```
3. Установите зависимости:
   ```bash
   sudo apt update
   sudo apt install -y python3-pip build-essential openjdk-17-jdk unzip zlib1g-dev libncurses5-dev libgdm-dev libsqlite3-dev libssl-dev libffi-dev
   pip install buildozer Cython
   ```
4. Соберите APK:
   ```bash
   buildozer -v android debug
   ```
5. Готовый APK будет в папке `bin/`: `bin/ordermanager-0.1-arm64-v8a-debug.apk`.

## 3. Docker

Если установлен Docker:

```bash
docker run --rm -v "%cd%":/home/user/hostcwd kivy/buildozer buildozer -v android debug
```

После сборки APK окажется в `bin/` внутри контейнера; при необходимости скопируйте его из образа или примонтируйте каталог `bin` как том.

## 4. Только проверка кода на ПК (без APK)

На Windows можно запускать приложение как обычное окно:

```bash
pip install kivy==2.3.0
python main.py
```

## Что сделано в коде

- **История заказов**: таблица «Дневная статистика» внизу экрана обёрнута в `ScrollView` с `do_scroll_x=True` и `do_scroll_y=True` — таблицу можно прокручивать по горизонтали и вертикали, видны все столбцы.
- **Анализ продаж**: таблица «Результаты анализа» также в прокручиваемой области с горизонтальной и вертикальной прокруткой.
- Высота областей с таблицами увеличена (`size_hint_y=0.5`), чтобы удобнее скроллить и видеть строки.

Функционал приложения сохранён; при сборке APK через buildozer он полностью переносится в мобильное приложение.
