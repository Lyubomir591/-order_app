[app]
title = OrderManager
package.name = ordermanager
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 0.1
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.arch = arm64-v8a
# Принять лицензии SDK без интерактива (для сборки в CI/скриптах)
android.accept_sdk_license = 1

[buildozer]
log_level = 2
warn_on_root = 1