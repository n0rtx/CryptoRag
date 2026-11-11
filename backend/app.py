"""Flask-приложение (WSGI): API + раздача собранного React-фронтенда."""
import logging

from flask import Flask, jsonify, request, send_from_directory

from . import config, ratelimit
from .coins import COINS
from .market import get_chart, get_market
from .rag import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cryptorag")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    pipeline.init()

    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin")
        if origin and origin in config.CORS_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Vary"] = "Origin"
        return resp

    def client_ip() -> str:
        # PythonAnywhere стоит за прокси: реальный IP в X-Forwarded-For
        fwd = request.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or request.remote_addr or "unknown"

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", index_ready=pipeline.store.ready, chunks=len(pipeline.store.meta),
                       openai_key=bool(config.OPENAI_API_KEY), filter_model=config.MODEL_PATH.exists())

    @app.get("/api/coins")
    def coins():
        return jsonify([{"symbol": s, "name": v[1]} for s, v in COINS.items()])

    @app.get("/api/price/<symbol>")
    def price(symbol: str):
        if not ratelimit.allow("p:" + client_ip(), config.RATE_LIMIT_PER_MIN * 3):
            return jsonify(error="rate_limited"), 429
        d = get_market(symbol.upper())
        return (jsonify(d), 200) if d else (jsonify(error="not_found"), 404)

    @app.get("/api/chart/<symbol>")
    def chart(symbol: str):
        if not ratelimit.allow("c:" + client_ip(), config.RATE_LIMIT_PER_MIN * 3):
            return jsonify(error="rate_limited"), 429
        days = min(max(request.args.get("days", 7, type=int), 1), 90)
        series = get_chart(symbol.upper(), days)
        return (jsonify(symbol=symbol.upper(), days=days, prices=series), 200) if series else (jsonify(error="not_found"), 404)

    @app.route("/api/ask", methods=["POST", "OPTIONS"])
    def ask():
        if request.method == "OPTIONS":
            return ("", 204)
        if not ratelimit.allow("a:" + client_ip(), config.RATE_LIMIT_PER_MIN):
            return jsonify(error="rate_limited", answer="Слишком много запросов. Подождите минуту."), 429
        data = request.get_json(silent=True) or {}
        question = str(data.get("question", ""))
        try:
            return jsonify(pipeline.answer(question))
        except RuntimeError as e:  # нет ключа и т.п.
            log.error("config error: %s", e)
            return jsonify(error="server_misconfigured", answer="Сервер не настроен (нет OPENAI_API_KEY)."), 500
        except Exception:
            log.exception("ask failed")
            return jsonify(error="internal", answer="Ошибка сервера при обработке запроса. Попробуйте позже."), 500

    # ---- Фронтенд (собранный Vite) ----
    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        if path.startswith("api/"):
            return jsonify(error="not_found"), 404
        dist = config.FRONTEND_DIST
        if path and (dist / path).is_file():
            return send_from_directory(dist, path)
        if (dist / "index.html").is_file():
            return send_from_directory(dist, "index.html")
        return "Frontend не собран: cd frontend && npm install && npm run build", 503

    return app


app = create_app()
