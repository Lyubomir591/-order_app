# Скрипт для отправки кода на GitHub и запуска сборки APK

Write-Host "=== Отправка кода на GitHub ===" -ForegroundColor Green
Write-Host ""

# Проверка текущего remote
Write-Host "Текущий remote:" -ForegroundColor Yellow
git remote -v
Write-Host ""

# Если нужно изменить URL репозитория, раскомментируйте и укажите правильное имя:
# git remote set-url origin https://github.com/Lyubomir591/order_app.git

Write-Host "Отправка кода на GitHub..." -ForegroundColor Yellow
Write-Host "ВНИМАНИЕ: GitHub попросит логин и пароль (или токен)" -ForegroundColor Cyan
Write-Host ""

# Пуш на GitHub
git push -u origin master

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== УСПЕХ! Код отправлен на GitHub ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Следующие шаги:" -ForegroundColor Yellow
    Write-Host "1. Откройте https://github.com/Lyubomir591/-order_app" -ForegroundColor White
    Write-Host "2. Перейдите на вкладку 'Actions'" -ForegroundColor White
    Write-Host "3. Выберите 'Build APK' → 'Run workflow' → 'Run workflow'" -ForegroundColor White
    Write-Host "4. Дождитесь завершения (30-50 минут первый раз)" -ForegroundColor White
    Write-Host "5. Скачайте APK из раздела 'Artifacts'" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "=== ОШИБКА при отправке ===" -ForegroundColor Red
    Write-Host "Возможные причины:" -ForegroundColor Yellow
    Write-Host "- Неверный URL репозитория (проверьте имя на GitHub)" -ForegroundColor White
    Write-Host "- Неверный логин/пароль" -ForegroundColor White
    Write-Host "- Репозиторий не существует на GitHub" -ForegroundColor White
    Write-Host ""
    Write-Host "Проверьте URL репозитория на GitHub и при необходимости выполните:" -ForegroundColor Cyan
    Write-Host "git remote set-url origin https://github.com/Lyubomir591/ПРАВИЛЬНОЕ_ИМЯ.git" -ForegroundColor White
}
