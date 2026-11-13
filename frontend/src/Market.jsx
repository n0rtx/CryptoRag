import { useEffect, useState } from "react";

const NAMES = { BTC: "Bitcoin", ETH: "Ethereum", SOL: "Solana", BNB: "BNB", XRP: "XRP", DOGE: "Dogecoin" };
const W = 320, H = 130, PAD = 8;

/**
 * Render a price series as an animated SVG sparkline.
 * @param {{prices: number[]|null, up: boolean, id: string}} props - Price series, trend direction and unique id.
 * @returns {JSX.Element} The chart, or a skeleton placeholder while data is loading.
 */
function Sparkline({ prices, up, id }) {
  if (!prices || prices.length < 2) return <div className="spark skeleton" />;
  const min = Math.min(...prices), max = Math.max(...prices), span = max - min || 1;
  const pts = prices.map((p, i) => [
    (i / (prices.length - 1)) * W,
    H - PAD - ((p - min) / span) * (H - PAD * 2),
  ]);
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  const color = up ? "var(--up)" : "var(--down)";
  const gid = `g-${id}`;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${id} 7d chart`}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.32" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon className="spark-fill" points={`0,${H} ${line} ${W},${H}`} fill={`url(#${gid})`} />
      <polyline className="spark-line" points={line} pathLength="1" fill="none" stroke={color}
        strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      <circle className="spark-pulse" cx={lx} cy={ly} r="4.5" fill={color} />
      <circle cx={lx} cy={ly} r="3.6" fill={color} />
    </svg>
  );
}

/**
 * Describe a refresh interval in Russian.
 * @param {number} seconds - Interval in seconds.
 * @returns {string} For example "2 ч" or "10 мин".
 */
function formatInterval(seconds) {
  if (seconds >= 3600) return `${Math.round(seconds / 360) / 10} ч`.replace(".0", "");
  return `${Math.max(1, Math.round(seconds / 60))} мин`;
}

/**
 * Grid of coin cards with cached prices and 7-day charts.
 * @param {{getMarket: Function}} props - Loader for the market overview.
 * @returns {JSX.Element} The market grid.
 */
export default function Market({ getMarket }) {
  const [overview, setOverview] = useState(null);

  useEffect(() => {
    let alive = true;
    let timer;
    /** Load the overview and poll quickly until all coins have data, then slowly. */
    const load = async () => {
      const data = await getMarket().catch(() => null);
      if (!alive) return;
      if (data) setOverview(data);
      const complete = data && data.coins.every((c) => c.price_usd !== null && c.prices);
      timer = setTimeout(load, complete ? 300000 : 15000);
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, []);

  const coins = overview?.coins ?? [];
  const updated = overview?.updated ? new Date(overview.updated) : null;
  const sources = [...new Set(coins.map((c) => c.source).filter(Boolean))];

  return (
    <>
      <div className="market">
        {coins.length === 0 && Array.from({ length: 6 }, (_, i) => <div key={i} className="tick"><div className="spark skeleton" style={{ height: 190 }} /></div>)}
        {coins.map((c, i) => {
          const ch = c.change_24h_pct;
          const series = c.prices;
          const trendUp = series ? series[series.length - 1] >= series[0] : (ch ?? 0) >= 0;
          const week = series ? (series[series.length - 1] / series[0] - 1) * 100 : null;
          return (
            <div key={c.symbol} className={`tick ${trendUp ? "t-up" : "t-down"}`} style={{ animationDelay: `${i * 80}ms` }}>
              <div className="tick-head">
                <div className="coin"><b>{c.symbol}</b><small>{c.name}</small></div>
                {typeof ch === "number" && (
                  <em className={`chip ${ch >= 0 ? "up" : "down"}`}>{ch >= 0 ? "▲" : "▼"} {Math.abs(ch).toFixed(2)}% <small>24ч</small></em>
                )}
              </div>
              <div className="price">{c.price_usd !== null ? `$${c.price_usd.toLocaleString("en-US", { maximumFractionDigits: c.price_usd < 1 ? 4 : 2 })}` : "—"}</div>
              <Sparkline prices={series} up={trendUp} id={c.symbol} />
              <div className="tick-foot">
                <span>7 дней</span>
                {week !== null && <span className={week >= 0 ? "up" : "down"}>{week >= 0 ? "+" : ""}{week.toFixed(2)}%</span>}
              </div>
            </div>
          );
        })}
      </div>
      {overview && (
        <div className="market-meta">
          {updated ? `Обновлено ${updated.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}` : "Данные загружаются…"}
          {sources.length > 0 && ` · ${sources.join(", ")}`}
          {` · обновление каждые ${formatInterval(overview.refresh_seconds)}`}
        </div>
      )}
    </>
  );
}
