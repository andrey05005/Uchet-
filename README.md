# Uchet-

## PWA иконки (SVG для этого окружения)
Сейчас манифест и `apple-touch-icon` используют SVG‑иконки, потому что бинарные файлы (PNG) недоступны в этом окружении.

Чтобы перейти на рекомендованные iOS PNG‑иконки:
1. Добавьте файлы `static/icons/icon-192.png` и `static/icons/icon-512.png`.
2. Обновите `static/manifest.webmanifest`, заменив пути на PNG и тип на `image/png`.
3. Обновите `<link rel="apple-touch-icon">` в `templates/base.html` на PNG.
