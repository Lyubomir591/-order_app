# Как получить APK за 3 шага

## Шаг 1. Создайте репозиторий на GitHub

1. Зайдите на https://github.com и войдите в аккаунт (или зарегистрируйтесь).
2. Нажмите **+** → **New repository**.
3. Название: например `order-app`. Репозиторий может быть **Private**.
4. **Не** ставьте галочки "Add README" и "Add .gitignore" — проект уже есть локально.
5. Нажмите **Create repository**.

## Шаг 2. Загрузите проект (один раз)

В терминале в папке проекта выполните (подставьте вместо `ВАШ_АККАУНТ` и `order-app` свои данные):

```powershell
cd c:\order-app

git init
git add .
git commit -m "Order Manager app"
git branch -M main
git remote add origin https://github.com/ВАШ_АККАУНТ/order-app.git
git push -u origin main
```

Если репозиторий уже создан и вы уже делали `git init` и `git remote add`, достаточно:

```powershell
git add .
git commit -m "Update"
git push
```

## Шаг 3. Соберите и скачайте APK

1. На GitHub откройте свой репозиторий → вкладка **Actions**.
2. Слева выберите **Build APK** → справа нажмите **Run workflow** → **Run workflow**.
3. Дождитесь зелёной галочки (первый раз 30–50 минут).
4. Нажмите на завершённый запуск → внизу в блоке **Artifacts** скачайте **ordermanager-apk**.
5. В архиве будет файл **.apk** — установите его на телефон.

Готово.
