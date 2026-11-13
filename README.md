# CryptoRAG

> A RAG chatbot for cryptocurrencies: ask about BTC, ETH, SOL and 20+ other coins and get answers grounded in a knowledge base and live CoinGecko data. A custom-trained ML filter blocks junk queries before they ever reach the OpenAI API. Built with Flask and React, designed to run on PythonAnywhere.

| | Link |
|---|---|
| 🌐 Deployed site | https://n0rt.pythonanywhere.com |

## 📖 About

CryptoRAG answers questions about cryptocurrencies: price, technology, tokenomics, consensus, risks. Instead of relying on the memory of a language model, every answer is built from retrieved knowledge-base excerpts and real-time market data, and the sources are shown under the reply.

The problem the project solves: a plain LLM chatbot hallucinates prices and facts, and every off-topic or malicious message costs money. CryptoRAG grounds its answers in real data and uses a lightweight trained classifier, rules, caching, and rate limiting to spend API tokens only on questions that deserve them.

## ✨ Features

- Chat with answers in Russian or English (the reply language follows the question)
- Retrieval-Augmented Generation over a markdown knowledge base with source attribution
- Market data from several sources (CoinGecko, Binance, Coinbase) with automatic fallback when one of them is down
- Background refresh on a schedule (every 2 hours by default); the last good data is stored on disk and survives restarts
- "Market" tab with cards and animated 7-day charts for the top coins
- Custom ML filter that rejects off-topic and junk questions without calling OpenAI
- Rule-based protection: length limit, prompt-injection patterns, link spam, gibberish
- Caching: answers (5 min), market snapshot (refreshed on a schedule), on-demand data for other coins (10 min)
- Rate limiting per IP address
- Markdown rendering in answers (lists, tables, code, links)
- Light and dark themes with the choice remembered in the browser
- Recognition of coins by ticker or name, including Russian aliases (биткоин, эфир, солана)

## 🎨 Design

A clean card-based interface with a graphite dark theme, a warm-white light theme, and a green accent. CSS-only animations (chart drawing, card reveal, typing indicator), a hidden scrollbar with scrolling preserved, and a responsive layout for desktop and mobile. The frontend is built into static files, so the server does no rendering work.

## 🏗️ Architecture

```
question
   │
   ├─ 1. Rules              length, injection, links, gibberish
   ├─ 2. ML filter          TF-IDF + Logistic Regression
   │        └─ junk ──────► canned refusal (no OpenAI call)
   ├─ 3. Answer cache
   ├─ 4. Coin detection ──► market snapshot (CoinGecko → Binance → Coinbase)
   ├─ 5. Embedding + vector search (top-k chunks)
   └─ 6. LLM answer grounded in the retrieved context
```

| Path | Responsibility |
|---|---|
| `backend/app.py` | Flask application, API routes, rate limiting, static frontend serving |
| `backend/config.py` | Settings loaded from `.env` |
| `backend/coins.py` | Coin registry, aliases, coin detection in text |
| `backend/providers.py` | Market-data providers: CoinGecko, Binance, Coinbase |
| `backend/market.py` | Provider fallback chain, disk snapshot, cached prices and charts |
| `backend/scheduler.py` | Background thread that refreshes market data periodically |
| `backend/ratelimit.py` | Sliding-window rate limiter |
| `backend/guard/` | Query filter: rules, classifier, training dataset generator |
| `backend/rag/` | Chunker, vector store, OpenAI client, RAG pipeline |
| `data/knowledge/` | Markdown knowledge base |
| `data/index/` | Prebuilt vector index |
| `models/` | Trained filter model (`query_filter.joblib`) |
| `scripts/` | `ingest.py` (build the index), `train_filter.py` (train the filter), `refresh_market.py` (refresh market data once) |
| `frontend/` | React + Vite single-page application |
| `wsgi.py` | WSGI entry point |

Patterns: Pipeline, Retrieval-Augmented Generation, Lazy Initialization, Cache-Aside, Sliding-Window Rate Limiting, Application Factory.

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| Backend | Python, Flask (WSGI), python-dotenv, requests |
| LLM | OpenAI API (`gpt-4o-mini`, `text-embedding-3-small`) |
| Retrieval | NumPy cosine-similarity search (no vector database) |
| ML filter | scikit-learn: TF-IDF (char + word n-grams), Logistic Regression, joblib |
| Market data | CoinGecko, Binance and Coinbase public APIs |
| Frontend | React 18, Vite, react-markdown, remark-gfm, plain CSS |
| Hosting | PythonAnywhere (WSGI) |

## 🧠 Query Filter

A binary classifier that decides whether a question is about crypto or junk, so that junk never costs an OpenAI call.

- **Features:** character n-grams (2–5), robust to typos and word forms, combined with word unigrams and bigrams
- **Model:** Logistic Regression with balanced class weights, returning a probability that is compared with `FILTER_THRESHOLD`
- **Size:** about 130 KB, runs on CPU in milliseconds, no torch or GPU required
- **Training data:** a generated bilingual (Russian and English) dataset of roughly 2,250 examples, including hard negatives such as "tell me about cats" that mirror crypto phrasing, injection attempts, spam, and keyboard noise
- **Coin boost:** an explicit coin mention raises the confidence to at least 0.6, so short queries like "sol price" are not rejected
- **Ambiguous words:** `link`, `near`, `sol`, `dot` count as coins only when written in capitals
- **Fine-tuning:** add real queries to `data/filter_extra.csv` (`label,text`; 1 = crypto, 0 = junk) and retrain

```bash
python scripts/train_filter.py
```

Metrics on the held-out split are near-perfect, but the dataset is synthetic, so real-world quality should be verified on genuine user queries.

## 📚 Knowledge Base

Markdown documents in `data/knowledge/` (Bitcoin, Ethereum, Solana, crypto basics) are split by headings and paragraphs into chunks of about 900 characters with overlap. Each chunk is embedded with OpenAI and stored in `data/index/` as a NumPy matrix plus JSON metadata. Chunks from the document about a coin mentioned in the question receive a small relevance boost.

`python scripts/ingest.py --coingecko` additionally downloads descriptions of all coins listed in `backend/coins.py`.

## 💹 Market Data

Prices and charts are not requested on every page view. A background thread refreshes them for the coins in `MARKET_SYMBOLS` every `MARKET_REFRESH_SECONDS` (7200 s by default) and writes a snapshot to `data/cache/market_snapshot.json`.

- **Fallback chain:** providers are tried in the order of `MARKET_PROVIDERS`. If CoinGecko fails or does not return a coin, Binance is tried, then Coinbase. A provider that just failed is skipped for a minute.
- **Persistence:** after a restart the snapshot is loaded from disk, so data is available immediately and the next refresh happens when the data reaches its refresh age.
- **Retries:** after a failed or partial refresh the thread retries after 5 minutes and only repeats what is missing.
- **Visibility:** every data block carries its source and timestamp, the Market tab shows the last update time and sources, and the chatbot names them in its answers.
- **Other coins:** coins outside `MARKET_SYMBOLS` are fetched on demand and cached for `MARKET_ONDEMAND_TTL` seconds.
- **Field coverage:** CoinGecko provides market cap, rank, supply, ATH and 7d / 30d changes. Binance and Coinbase provide price, 24h change, range and volume only, and missing fields are simply omitted from the answer context.

To refresh without relying on the web process (for example as a PythonAnywhere scheduled task), run:

```bash
python scripts/refresh_market.py
```

## ⚙️ Configuration

All settings come from environment variables (`.env`, template in `.env.example`).

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (required) |
| `OPENAI_CHAT_MODEL`, `OPENAI_EMBED_MODEL` | Chat and embedding models |
| `COINGECKO_API_KEY`, `COINGECKO_BASE_URL` | Optional CoinGecko key and API base URL |
| `MARKET_PROVIDERS` | Provider priority, for example `coingecko,binance,coinbase` |
| `MARKET_SYMBOLS` | Coins shown on the Market tab and refreshed in the background |
| `MARKET_REFRESH_SECONDS` | Background refresh interval (default 7200) |
| `MARKET_ONDEMAND_TTL` | Cache lifetime for coins outside `MARKET_SYMBOLS` |
| `MARKET_BACKGROUND` | Set to `false` to disable the background thread |
| `BINANCE_BASE_URL`, `COINBASE_BASE_URL` | API base URLs (use `https://data-api.binance.vision/api/v3` if Binance is blocked in your region) |
| `FILTER_THRESHOLD` | Minimum probability for a question to be allowed (default 0.5) |
| `MAX_QUESTION_CHARS` | Maximum question length |
| `RAG_TOP_K`, `RAG_MIN_SCORE` | Number of retrieved chunks and minimum similarity |
| `ANSWER_CACHE_TTL` | Answer cache lifetime in seconds |
| `RATE_LIMIT_PER_MIN` | Requests per minute per IP |
| `CORS_ORIGINS` | Allowed origins when the frontend is hosted separately |

Secrets are provided only via `.env`, which is excluded from the repository.

## 🚀 Getting Started

Requires Python 3.10+ and Node.js (Node is only needed to rebuild the frontend).

```bash
git clone <repository-url>
cd CryptoRag

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python scripts/ingest.py --coingecko
python wsgi.py
```

Open http://127.0.0.1:5000. The API and the built frontend are served from the same port. Check `/api/health` to confirm that the index is loaded.

Frontend development with hot reload (in a separate terminal):

```bash
cd frontend
npm install
npm run dev
```

Rebuild the frontend for production:

```bash
cd frontend
npm run build
```

## ☁️ Deployment on PythonAnywhere

1. Locally: build the index (`python scripts/ingest.py --coingecko`) and the frontend (`npm run build`), then commit `data/index/`, `models/`, and `frontend/dist/`. PythonAnywhere does not build the frontend.
2. In a PythonAnywhere Bash console:
   ```bash
   git clone <repository-url>
   cd CryptoRag
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   nano .env
   ```
3. On the **Web** tab, create a web app with **Manual configuration** and pick the same Python version as the virtualenv.
   - **Virtualenv:** `/home/<user>/CryptoRag/.venv`
   - **WSGI configuration file:**
     ```python
     import sys
     path = "/home/<user>/CryptoRag"
     if path not in sys.path:
         sys.path.insert(0, path)
     from wsgi import application
     ```
   - Press **Reload** and open `/api/health`.
4. To update: `git pull` in the console, then **Reload**.

Notes for the free tier: outgoing traffic is limited to a whitelist (`api.openai.com`, `api.coingecko.com`, `api.binance.com` and `api.coinbase.com` are on it, so the fallback chain works), the background refresh thread runs inside the web worker, and you can add `python scripts/refresh_market.py` as a scheduled task to keep the snapshot fresh while the app is idle, there is a single worker so in-memory caches and rate limits are consistent, the disk is small, which is why the project avoids heavy dependencies such as torch or a vector database, and a free web app must be extended periodically from the Web tab.

## 🔒 Security

- Prompt-injection patterns are blocked before the model is called, and the system prompt instructs the LLM to ignore instructions embedded in questions or context
- The LLM answers only from the provided context and never gives personalized financial advice
- Question length limit and per-IP rate limiting
- React escapes output, and markdown is rendered without raw HTML
- Secrets only in `.env`

## 📡 API

| Endpoint | Description |
|---|---|
| `POST /api/ask` | Body `{ "question": "..." }`. Returns `answer`, `sources`, `coins`, `market`, `blocked`, `reason` |
| `GET /api/market` | Cached prices and 7-day charts for all tracked coins, with update time and sources |
| `GET /api/price/<SYMBOL>` | Market data for a coin, with source and timestamp |
| `GET /api/chart/<SYMBOL>?days=7` | Price series for a chart (1–90 days) |
| `GET /api/coins` | List of supported coins |
| `GET /api/health` | Service status: index, API key, filter model, last market update |

## 🗺️ Roadmap

- [ ] Conversation history for follow-up questions
- [ ] Larger knowledge base and automatic refresh
- [ ] Fine-tune the filter on real user queries
- [ ] Answer streaming (requires an ASGI-capable host)
- [ ] Automated tests and CI

## 📄 License

MIT. See the [LICENSE](LICENSE) file.
