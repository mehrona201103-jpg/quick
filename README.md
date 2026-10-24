# QUICK TRADER AI V3 — обновлённая сборка

## Изменения в этой версии
- Переработан WebApp: тёмный monochrome iOS-like glass UI, размытие и отражения, мягкие анимации, анимированный свечной фон-обои, отдельные разделы «Терминал», «История», «Профиль».
- График свечей по OHLC-данным перезапрашивается каждые 20 секунд, пока WebApp открыт; кэш сервера уменьшает повторные запросы к поставщику примерно до одного запроса на инструмент/интервал в 55 секунд. Обновление зависит от доступности API и лимитов провайдера.
- Таймфрейм начинается с 1m. Экспирации: `5s`, `15s`, `30s`, `1m`, `5m`, `10m`, `15m`, `30m`, `1d`.
- Удалена нижняя постоянная клавиатура бота. Управление регистрацией и переходы по разделам бота идут через inline-кнопки.
- Регистрация: `/start` → проверка подписки на `@quick_app_official` → ссылка на регистрацию Pocket Option и промокод → «Я зарегистрировался» → ввод Pocket Option ID → автоматическое сохранение и открытие WebApp.
- Текущий шаг регистрации сохраняется в SQLite. Пользовательские данные и история сигналов сохраняются между рестартами, если база находится на постоянном диске.
- Добавлена миграция для старой SQLite-схемы с новым полем `registration_step`.

## Переменные окружения
Скопируйте `.env.example` в `.env` локально или задайте те же переменные в панели хостинга:
- `BOT_TOKEN` — токен Telegram-бота.
- `ADMIN_IDS` — Telegram ID администраторов, через запятую.
- `ADMIN_PANEL_TOKEN` — длинный случайный токен для приватного endpoint статистики.
- `WEBAPP_URL` — публичный HTTPS URL WebApp.
- `TWELVE_DATA_API_KEY` — ключ Twelve Data для свечей и технического анализа.
- `DATABASE_PATH` — путь к SQLite. На Render укажите каталог постоянного диска.
- `CHANNEL_USERNAME` и `CHANNEL_URL` — канал, на который нужно подписаться.
- `POCKET_OPTION_REFERRAL_URL` и `POCKET_OPTION_PROMO_CODE` — referral link и промокод.

## Установка и Render
1. Python 3.11+.
2. `pip install -r requirements.txt`.
3. Установить переменные окружения из `.env.example` (не отправляйте `.env` в GitHub).
4. Build Command: `pip install -r requirements.txt`.
5. Start Command: `python run_all.py`.
6. Telegram WebApp требует HTTPS. Убедитесь, что `WEBAPP_URL` ведёт на публичный URL приложения.
7. Чтобы бот мог проверять подписку на канал, добавьте бота в канал администратором и настройте правильный `CHANNEL_USERNAME`.
8. Для Render подключите persistent disk и задайте `DATABASE_PATH` например `/var/data/quick_trader.db`, где `/var/data` — точка монтирования вашего диска. Иначе данные могут пропасть при пересоздании экземпляра.
9. Один экземпляр приложения запускает polling бота и HTTP-сервер вместе. Не запускайте несколько одинаковых polling-процессов с одним BOT_TOKEN.

## Сигналы и ограничения
- Сигналы используют EMA 9/21, RSI и импульс. Это простая индикаторная эвристика, не статистически проверенный прогноз.
- Показатель «сила совпадения» — это не процент вероятности выигрыша. Для отображения win rate нужно собирать и проверять реальные исходы сигналов.
- `5s`, `15s`, `30s` и другие сроки экспирации показываются как выбор пользователя; источник предоставляет свечи с поддерживаемыми интервалами и не гарантирует тиковые данные на секунды.
- Котировки Twelve Data — обычный Forex/поддерживаемые инструменты, не OTC-цены Pocket Option. Не все символы из списка будут доступными в каждом аккаунте/тарифе поставщика.
- Кнопка «Я зарегистрировался» опирается на действие пользователя; приложение не может самостоятельно подтвердить регистрацию на стороне брокера. Автоматический доступ после Pocket Option ID также не доказывает владельца ID.
- Рекламные условия бонуса, в том числе возможность бонуса до 50%, могут зависеть от брокера, страны, депозита и текущих правил. Перед публикацией проверьте актуальные условия у Pocket Option.

## API
- `GET /api/webapp/config`
- `GET /api/webapp/profile?tg_id=...`
- `GET /api/webapp/history?tg_id=...`
- `POST /api/webapp/analyze`
- `GET /api/webapp/chart?symbol=EUR/USD&timeframe=1m`
- `GET /admin/stats?token=...` (`ADMIN_PANEL_TOKEN` нужно отдельно задать для этого endpoint)


## V4 trial / VIP payments
- Persistent 72-hour trial starts at first successful account activation. Expired trials are blocked server-side from signal analysis and shown the tariff paywall in WebApp.
- Telegram Stars invoices use XTR and activate VIP after Telegram's successful_payment update.
- CryptoBot invoices are checked against Crypto Pay API before activating VIP; set `CRYPTOPAY_TOKEN`. `BOT_USERNAME` is required for the WebApp tariff button to deep-link to the bot.
- Plans: $5/200 Stars for 1 month; $10/400 Stars for 6 months; $20/900 Stars for 6 months Premium, as requested.
- Author gift button opens the author's Telegram profile using `AUTHOR_TELEGRAM_ID`; Telegram handles whether gifts can be sent to that profile.
- Configure `BOT_USERNAME`, `AUTHOR_TELEGRAM_ID`, and `CRYPTOPAY_TOKEN` in Render environment. Test payments before going live.


## V5: persistent database and admin commands

### Render: keep user accounts and subscriptions

1. Create a PostgreSQL database in Render (or use another managed PostgreSQL provider).
2. In the Web Service environment variables, set `DATABASE_URL` to the database's **Internal Database URL** when both services are in Render. For other providers, use their connection URL.
3. Keep `DATABASE_PATH` only for local SQLite development; when `DATABASE_URL` is set to a PostgreSQL URL, the app uses PostgreSQL automatically.
4. Deploy the service and verify logs show no database connection errors. The app creates its tables on startup.

**Important:** Render's free PostgreSQL databases are temporary and may expire under Render's current free-tier policy. For long-term account retention, use a database plan with persistent retention/backups or another managed PostgreSQL service. The free web service may still sleep and take time to wake; PostgreSQL prevents user data from being tied to the web service's temporary filesystem.

### Admin commands (only IDs in `ADMIN_IDS`)

- `/admin` — overview and command list
- `/stats` — user, access, VIP, blocked and signal totals
- `/users` — latest 20 users
- `/user TELEGRAM_ID` — user profile
- `/approve TELEGRAM_ID` — grant base access
- `/revoke TELEGRAM_ID` — revoke base access
- `/grantvip TELEGRAM_ID DAYS` — grant VIP for 1–3650 days
- `/revokevip TELEGRAM_ID` — revoke VIP
- `/block TELEGRAM_ID` and `/unblock TELEGRAM_ID` — block/unblock a user
- `/events` — recent admin actions

On `/start`, the bot now removes any old persistent reply keyboard and uses inline buttons inside messages instead. WebApp identity remains verified against Telegram's signed `initData`; do not bypass this check.
