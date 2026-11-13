import logging

from flask import Flask, jsonify, request, send_from_directory

from . import config, market, ratelimit, scheduler
from .coins import COINS
from .market import get_chart, get_market
from .rag import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cryptorag")


def create_app() -> Flask:
    """Create and configure the Flask application.

    Registers the API routes, CORS handling and the static frontend, and loads the vector index.

    Returns:
        The configured Flask application.
    """
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    pipeline.init()
    market.load()
    scheduler.start()

    @app.after_request
    def cors(resp):
        """Add CORS headers for origins listed in the configuration.

        Args:
            resp: The outgoing response.

        Returns:
            The response with CORS headers when the origin is allowed.
        """
        origin = request.headers.get("Origin")
        if origin and origin in config.CORS_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Vary"] = "Origin"
        return resp

    def client_ip() -> str:
        """Determine the client IP address, honouring the proxy header.

        Returns:
            The client IP address as a string.
        """
        fwd = request.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or request.remote_addr or "unknown"

    @app.get("/api/health")
    def health():
        """Report service status.

        Returns:
            JSON with index, API key and filter model availability.
        """
        return jsonify(status="ok", index_ready=pipeline.store.ready, chunks=len(pipeline.store.meta),
                       openai_key=bool(config.OPENAI_API_KEY), filter_model=config.MODEL_PATH.exists(),
                       market_updated=market.get_overview()["updated"])

    @app.get("/api/coins")
    def coins():
        """List the supported coins.

        Returns:
            JSON array of symbols and names.
        """
        return jsonify([{"symbol": s, "name": v[1]} for s, v in COINS.items()])

    @app.get("/api/price/<symbol>")
    def price(symbol: str):
        """Return live market data for one coin.

        Args:
            symbol: Ticker symbol from the URL.

        Returns:
            JSON market data, 404 if unknown, or 429 when rate limited.
        """
        if not ratelimit.allow("p:" + client_ip(), config.RATE_LIMIT_PER_MIN * 3):
            return jsonify(error="rate_limited"), 429
        d = get_market(symbol.upper())
        return (jsonify(d), 200) if d else (jsonify(error="not_found"), 404)

    @app.get("/api/market")
    def market_overview():
        """Return cached prices and 7-day charts for all tracked coins in one response.

        Returns:
            JSON with the last update time, the refresh interval and a list of coins, or 429 when rate limited.
        """
        if not ratelimit.allow("o:" + client_ip(), config.RATE_LIMIT_PER_MIN * 3):
            return jsonify(error="rate_limited"), 429
        return jsonify(market.get_overview())

    @app.get("/api/chart/<symbol>")
    def chart(symbol: str):
        """Return a price series for a coin.

        Args:
            symbol: Ticker symbol from the URL.

        Returns:
            JSON with the price list, 404 if unavailable, or 429 when rate limited.
        """
        if not ratelimit.allow("c:" + client_ip(), config.RATE_LIMIT_PER_MIN * 3):
            return jsonify(error="rate_limited"), 429
        days = min(max(request.args.get("days", 7, type=int), 1), 90)
        series = get_chart(symbol.upper(), days)
        return (jsonify(symbol=symbol.upper(), days=days, prices=series), 200) if series else (jsonify(error="not_found"), 404)

    @app.route("/api/ask", methods=["POST", "OPTIONS"])
    def ask():
        """Answer a user question through the RAG pipeline.

        Returns:
            JSON with the answer, sources and metadata. Responds with 429 when rate limited and 500 on server errors.
        """
        if request.method == "OPTIONS":
            return ("", 204)
        if not ratelimit.allow("a:" + client_ip(), config.RATE_LIMIT_PER_MIN):
            return jsonify(error="rate_limited", answer="Слишком много запросов. Подождите минуту."), 429
        data = request.get_json(silent=True) or {}
        question = str(data.get("question", ""))
        try:
            return jsonify(pipeline.answer(question))
        except RuntimeError as e:
            log.error("config error: %s", e)
            return jsonify(error="server_misconfigured", answer="Сервер не настроен (нет OPENAI_API_KEY)."), 500
        except Exception:
            log.exception("ask failed")
            return jsonify(error="internal", answer="Ошибка сервера при обработке запроса. Попробуйте позже."), 500

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str):
        """Serve the built React frontend with a single-page-app fallback.

        Args:
            path: Requested path.

        Returns:
            The requested static file, ``index.html``, or an error response.
        """
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
