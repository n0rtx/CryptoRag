# CryptoRAG

RAG-чатбот по криптовалютам (BTC, ETH, SOL и ещё ~20 монет). Бэкенд — Python/Flask, фронтенд — React (Vite), LLM — OpenAI API. Спроектирован под хостинг на **PythonAnywhere** (чистый WSGI, никаких тяжёлых зависимостей вроде torch/faiss/chroma).

## Как это работает

```
вопрос ─► правила (длина, injection, мусор)
        ─► ML-фильтр (TF-IDF + LogisticRegression, ~130 КБ, обучен локально)   ── мусор → отказ БЕЗ вызова OpenAI
        ─► кэш ответов (TTL 5 мин)
        ─► распознавание монет (BTC/биткоин/SOL…) ─► живые данные CoinGecko (кэш 60 с)
        ─► эмбеддинг вопроса (OpenAI) ─► поиск по numpy-индексу (cosine) ─► top-k чанков
        ─► gpt-4o-mini: ответ строго по контексту, на языке вопроса
```

Экономия токенов: правила → ML-фильтр → кэш ответов → rate limit (10 зап/мин на IP). Только запросы «про крипту» доходят до OpenAI.

## Структура

```
backend/        Flask-приложение (app.py), RAG (rag/), фильтр (guard/), CoinGecko (market.py), список монет (coins.py)
data/knowledge/ markdown-база знаний (btc, eth, sol, general) — добавляйте свои .md
data/index/     готовый векторный индекс (создаётся scripts/ingest.py, коммитится)
models/         обученный фильтр query_filter.joblib (коммитится)
frontend/       React + Vite; собранный frontend/dist коммитится (на PythonAnywhere нет сборки)
scripts/        ingest.py (индекс), train_filter.py (обучение фильтра)
wsgi.py         точка входа WSGI
```

## Локальный запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # впишите OPENAI_API_KEY
python scripts/train_filter.py  # обучить фильтр (уже лежит готовый в models/)
python scripts/ingest.py        # построить индекс (--coingecko добавит описания всех монет из coins.py)
python wsgi.py                  # http://127.0.0.1:5000  (API + фронт)
```

Разработка фронтенда с hot-reload: `cd frontend && npm install && npm run dev` (проксирует `/api` на :5000).
Пересборка для продакшна: `cd frontend && npm run build` → закоммитить `frontend/dist`.

## Деплой на PythonAnywhere

1. **Локально** (на вашем компьютере, где есть Node и ключ):
   `python scripts/ingest.py --coingecko` и `cd frontend && npm run build`, затем закоммитьте `data/index/`, `models/`, `frontend/dist/` и запушьте в GitHub.
2. **На PythonAnywhere** → вкладка *Consoles* → Bash:
   ```bash
   git clone https://github.com/<you>/CryptoRag.git
   cd CryptoRag
   mkvirtualenv --python=/usr/bin/python3.12 cryptorag   # версия — любая из доступных на аккаунте (3.10–3.13)
   pip install -r requirements.txt
   cp .env.example .env && nano .env                      # впишите OPENAI_API_KEY
   ```
3. Вкладка *Web* → **Add a new web app** → *Manual configuration* (не Flask!) → ваша версия Python.
   - **Virtualenv**: `/home/<user>/.virtualenvs/cryptorag`
   - **WSGI configuration file** — замените всё содержимое на:
     ```python
     import sys
     path = "/home/<user>/CryptoRag"
     if path not in sys.path:
         sys.path.insert(0, path)
     from wsgi import application
     ```
   - Нажмите **Reload**. Приложение: `https://<user>.pythonanywhere.com` (проверка: `/api/health`).
4. Обновление: `git pull` в консоли → **Reload** на вкладке Web.

### Ограничения PythonAnywhere, учтённые в проекте
- Только WSGI (нет websockets/ASGI) → простой POST `/api/ask`, без стриминга.
- Бесплатный аккаунт: исходящий трафик только на whitelist-хосты. `api.openai.com` в списке есть; **проверьте, что есть и `api.coingecko.com`** ([список](https://help.pythonanywhere.com/pages/WhitelistedSites/)). Если нет — живые цены не придут (бот ответит по базе знаний), либо нужен платный аккаунт.
- Диск 512 МБ и нет GPU → поэтому фильтр — scikit-learn, а векторный поиск — numpy; индекс и модель собираются локально и коммитятся.
- Free: 1 воркер → rate-limit и кэш в памяти процесса работают корректно. При нескольких воркерах лимиты будут «на воркер».
- Бесплатное приложение нужно раз в 3 месяца продлевать кнопкой на вкладке Web.

## Настройка и улучшение фильтра

- `FILTER_THRESHOLD` (.env) — чем выше, тем строже отсев (0.5 по умолчанию).
- Обучающая выборка синтетическая (`backend/guard/dataset.py`, RU+EN). Чтобы подстроить под реальные запросы, добавьте их в `data/filter_extra.csv` (`label,text`; 1 = крипта, 0 = мусор) и перезапустите `python scripts/train_filter.py`.
- Фильтр без истории диалога: короткие уточнения вроде «а что с ценой?» без названия монеты могут быть отклонены.

## Добавление монет и знаний
- Монета: добавьте строку в `backend/coins.py` (тикер, CoinGecko id, алиасы), затем `python scripts/ingest.py --coingecko`.
- Знания: положите `.md` в `data/knowledge/` (имя `xyz.md` = тикер → буст релевантности) и перезапустите `ingest.py`.

## API
- `POST /api/ask` `{ "question": "..." }` → `{ answer, sources, coins, market, blocked, reason }`
- `GET /api/price/<SYMBOL>`, `GET /api/coins`, `GET /api/health`

*Не является финансовой рекомендацией.*
