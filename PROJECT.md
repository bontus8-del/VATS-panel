# Exolve Panel — паспорт проекта

## Что это
GUI-панель (customtkinter) для работы с MTS Exolve CRM API.
Домен и RPS хранятся в `vats_config.json` рядом с `main.py`, ключ X-API-KEY — в Windows Credential Manager (через `keyring`).

## Стек
- Python 3.8+ (для Windows 7 — Python 3.8.10)
- customtkinter
- keyring < 24 (`pip install "keyring<24"`)
- pillow (опционально; только для фолбэка иконки окна через PNG)
- stdlib: `urllib.request`, `json`, `threading`, `re`, `random`, `time`, `os`, `sys`, `datetime`, `tkinter`

## Структура
```
exolve_panel/
├── main.py
├── config.py
├── assets/
│   ├── icon.ico
│   └── logo.png (опц.)
├── api/
│   ├── __init__.py
│   └── client.py
└── ui/
    ├── __init__.py
    ├── app.py
    ├── header.py
    ├── hotkeys.py
    ├── widgets/
    │   ├── __init__.py
    │   ├── toast.py
    │   ├── status_bar.py
    │   ├── pagination.py
    │   ├── autocomplete.py
    │   ├── tooltip.py
    │   └── route_dialog.py
    └── tabs/
        ├── __init__.py
        ├── base_tab.py
        ├── users_tab.py
        ├── nums_tab.py
        ├── replace_tab.py
        └── debug_tab.py
```

## Палитра (config.py)
RED_ACCENT #ff0033 / RED_HOVER #d6002b / DARK_HEADER #111827 / BG_MAIN #f8fafc /
CARD_BG #ffffff / TEXT_MAIN #0f172a / TEXT_MUTED #64748b / BORDER_COLOR #e2e8f0 /
ROW_BG_NORMAL #f8fafc / ROW_BG_SELECTED #e0f2fe / ROW_BORDER_SELECTED #38bdf8

## Пути (config.py)
- `_base_dir()` — `_MEIPASS` в PyInstaller `--onefile`, иначе папка исходников
- `_config_dir()` — рядом с exe при сборке, иначе папка исходников
- `APP_DIR`, `ASSETS_DIR = APP_DIR/assets`, `CONFIG_FILE = _config_dir()/vats_config.json`
- `asset_path(filename) -> str`

## Хранение учётных данных и настроек
- `config.load_domain() / save_domain(domain)` — JSON, поле `domain`
- `config.load_rps() / save_rps(rps)` — JSON, поле `rps` (int, 1..50), по умолчанию 5
- `config.load_key(domain) / save_key(domain, key) / delete_key(domain)` — keyring
- `config.keyring_available() -> bool`
- `config.DEFAULT_RPS = 5`, `MIN_RPS = 1`, `MAX_RPS = 50`
- JSON-хелперы: `_load_json` / `_save_json`

## Публичные API ExolveClient (`api/client.py`)
- `__init__(domain, key, timeout=10, max_rps=DEFAULT_RPS)`
- **Rate limit** — `_RateLimiter` (token interval), `set_rps(rps)`
- **Ретраи**: `MAX_ATTEMPTS=3`, backoff 0.5→8 с, Retry-After для 429 (cap 30 с)
- **Ошибки** → `ExolveApiError(message, status_code=None, retryable=False, retry_after=None, body=None)`
  - **`body`** — сырое тело ответа сервера (для 400/422 и т.п.); обрезается до `ERROR_BODY_MAX = 500` символов
  - Тексты: домен/соединение/не-JSON/404 → `DOMAIN_ERROR_MSG`; 400 → «Некорректный запрос (400)»; 422 → «Ошибка валидации (422)»; 401/403/429/5xx — как раньше
  - В `str(e)` тело ответа встраивается однострочно (до 200 символов)

### Методы
- `get_users()` → GET `/crmapi/v1/users/`
- `get_groups()` → GET `/crmapi/v1/groups`
- `get_telnums()` → GET `/crmapi/v1/telnums` (поле `disabled`)
- `enable_telnum(telnum)` → POST `/crmapi/v1/telnums/{telnum}/enabled`
- `disable_telnum(telnum)` → DELETE `/crmapi/v1/telnums/{telnum}/enabled`
- `set_telnum_route(telnum, params)` → POST `/crmapi/v1/telnums/{telnum}`
  - **Отправляем минимальный body**: `{type, user|group, disabled}` — без `user_name`/`group_name`
  - `disabled: false` включает приём звонков **одним запросом** (отдельный `/enabled` не нужен)
- `bind_telnum(login, telnum)` → POST `/crmapi/v1/caller-ids/users`

## VatsApp (`ui/app.py`)
- `domain_var`, `key_var`, `rps_var`
- `_load_persisted_credentials()` / `_do_save()` (дебаунс 500 мс)
- `get_client()`, `run_async(fn, on_done=None)`
- **`handle_api_error(e)`**:
  - 401 → `flash_key_error` + тост
  - если у ошибки есть `body` — выводит его в DebugTab (`set_raw`)
  - показывает тост + `set_status("Ошибка запроса", "error")`
- `_apply_window_icon()`, `set_status / set_debug_raw / copy_to_clipboard`
- Тосты: `ToastManager(self, top_offset=90)`

## Header (`ui/header.py`)
- Брендинг: 📞 + «ВАТС Панель» + бейдж MTC EXOLVE
- Поля: **⚙ МАКС. RPS** (70px), **🌐 ДОМЕН ВАТС** (210px), **🔑 КЛЮЧ** (230px)
- `flash_key_error(duration_ms=3000)`

## Виджеты (`ui/widgets/`)
- **ToastManager** — правый-верхний, ручное закрытие warning/error
- **StatusBar** — `set_status(text, kind)`
- **PaginationBar** — `set_total(n, reset_page=False)`, `go_to(p)`, `slice(items)`,
  `total_pages`, `page`, `page_size`
- **AutocompleteEntry** — `search/format/select`, `placeholder`, `tooltip_text`,
  `show_all_on_focus`, debounce 250 мс, `_suppress_change`
- **Tooltip**
- **RouteDialog** — модальный, две вкладки (👤 / 👥), `result` — dict или None

## Вкладка Users
- Пагинация + debounce 350 мс + сброс скролла `after_idle`

## Вкладка «Номера ВАТС»
- API: `/crmapi/v1/telnums`, поле `disabled`
- **Колонки**: `[✓] | Номер | Название | Маршрут | Статус | Действие`
- **Маршрут**: `user` → `👤 {name} ({login})`, `group` → `👥 {name} ({id})`,
  ivr/scheduler/fax/etc. → иконка+подпись, пусто → «— не задан»
- **Выделение** `_selected: set[str]`, сохраняется между страницами
- **Панель массовых действий**:
  - `☑ Выделить всё / ☐ Снять выделение`
  - `⋮` — «Выделить включенные», «Выделить отключенные», «Снять выделение»
    - обе «Выделить …» сначала делают `clear()`
  - `Выбрано: N`
  - **Единая кнопка массового действия**: меняет текст/цвет/команду
- **Кнопка в строке**: enabled → `disable_telnum`; disabled+маршрут → `enable_telnum`;
  disabled+нет маршрута → RouteDialog → set_route с `disabled: false`

### Объединение запросов (важно)
Когда нужно и задать маршрут, и включить номер — **один** вызов
`POST /telnums/{telnum}` с телом `{"type": ..., "user|group": ..., "disabled": false}`.
**Не вызываем** `/enabled` отдельно — иначе сервер возвращает 400 «уже включено».

### Потокобезопасность
`_bulk_enable` / `_bulk_disable` выполняются в daemon-потоке.
**Финализация (`_finalize_bulk`) выполняется в главном потоке** через `app.after(0, ...)`:
- обновление `raw_nums_data`
- вывод отчёта в DebugTab
- показ тоста
- `_render_page()`

Это критично: Tk-виджеты нельзя создавать/удалять из фоновых потоков.

### Прогресс
Статус-бар обновляется с троттлингом `PROGRESS_THROTTLE_S = 0.3` — не чаще 300 мс,
чтобы не «дёргать» интерфейс на быстрых операциях.

### Кэш групп
`self._groups_cache` — на сессию вкладки; сбрасывается в `load()`.

### Отчёт
Массовые операции → `{"timestamp","action","route","total","ok","failed","items"}` в DebugTab.

## Вкладка «Замена номеров»
- Поля логина и номера — `AutocompleteEntry`
- `execute` → последовательный `bind_telnum`, частоту регулирует rate-limiter
- Отчёт в DebugTab; сводка — тостами

## Что сделано
- Модульная структура; домен в JSON, ключ в keyring, RPS в JSON + поле в шапке
- Валидация домена и ключа (ASCII)
- Различение ошибок 400/401/403/404/422/429/5xx; тело ответа в ошибке
- Подсветка ключа при 401; тело ошибки в DebugTab
- Хоткеи: снятие нативных биндингов, матч по keycode, обе раскладки
- Ретраи с backoff + Retry-After; клиентский rate-limiter
- Тосты, статус-бар
- Пагинация Users/Nums; debounce 350 мс; сброс скролла
- Автодополнение логина/номера в Replace
- Иконка окна из `assets/icon.ico` (фолбэк `assets/logo.png`)
- `asset_path()`, `_base_dir()/_config_dir()` для PyInstaller
- Вкладка Номера: новый API, колонки «Название» и «Маршрут»
- Выделение чекбоксами (между страницами), массовые кнопки
- Единая кнопка массового действия
- RouteDialog (модальный, две вкладки)
- Реальные действия номера; **один запрос** при включении с маршрутом
- Кэш групп; прогресс с троттлингом; финализация в главном потоке
- **Тело ответа сервера доступно через `ExolveApiError.body` и выводится в DebugTab**

## Техдолг
1. Логирование в файл с ротацией
2. Отмена запроса
3. Явный connect/read timeout
4. Хоткеи macOS
5. Кеш между запусками
6. Сборка в exe (PyInstaller) + SmartScreen
7. Массовая операция не сбрасывает пагинацию

## Планы
1. Фаза 4 (продолжение): редактирование пользователя, экспорт CSV, тёмная тема
2. Сборка в exe (PyInstaller) + SmartScreen

## Соглашения по коду
- Русский язык: комментарии, UI, docstring'и
- 4 пробела
- Никаких print() — только тосты/диалоги/логи
- Импорты: stdlib → сторонние → локальные
- Все сетевые вызовы — только через `ExolveClient`
- UI — только в главном потоке через `app.after`
- Ключ **никогда** не попадает в текст ошибок, логи, DebugTab
- **Tk-виджеты нельзя создавать/удалять из фоновых потоков** — только через `app.after(0, ...)`

## Правило выдачи PROJECT.md
**При каждом изменении любых файлов проекта обязательно выдавать новую полную версию `PROJECT.md`** в том же ответе, чтобы пользователь мог её сохранить целиком.

## Как я хочу, чтобы ты отвечал
- Правишь файл — давай целиком
- Добавляешь файл — полный путь от `exolve_panel/`
- Не меняй поведение, о котором не просили
- Видишь проблему — скажи, но не «улучшай» без спроса
- По-русски, кратко, без воды