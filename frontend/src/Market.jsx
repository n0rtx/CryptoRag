import { useEffect, useState } from "react";

const NAMES = { BTC: "Bitcoin", ETH: "Ethereum", SOL: "Solana", BNB: "BNB", XRP: "XRP", DOGE: "Dogecoin" };
const W = 320, H = 130, PAD = 8;

// SVG-спарклайн без библиотек; анимация «рисования» — чистый CSS
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

export default function Market({ symbols, getPrice, getChart }) {
  const [data, setData] = useState({});
  const [charts, setCharts] = useState({});

  useEffect(() => {
    let alive = true;
    const loadPrices = async () => {
      const res = await Promise.all(symbols.map((s) => getPrice(s).catch(() => null)));
      if (alive) setData(Object.fromEntries(symbols.map((s, i) => [s, res[i]])));
    };
    const loadCharts = async () => {
      const res = await Promise.all(symbols.map((s) => getChart(s, 7).catch(() => null)));
      if (alive) setCharts(Object.fromEntries(symbols.map((s, i) => [s, res[i]])));
    };
    loadPrices();
    loadCharts();
    const p = setInterval(loadPrices, 60000);
    const c = setInterval(loadCharts, 600000);
    return () => { alive = false; clearInterval(p); clearInterval(c); };
  }, []);

  return (
    <div className="market">
      {symbols.map((s, i) => {
        const d = data[s];
        const ch = d?.change_24h_pct;
        const series = charts[s];
        const trendUp = series ? series[series.length - 1] >= series[0] : (ch ?? 0) >= 0;
        const week = series ? (series[series.length - 1] / series[0] - 1) * 100 : null;
        return (
          <div key={s} className={`tick ${trendUp ? "t-up" : "t-down"}`} style={{ animationDelay: `${i * 80}ms` }}>
            <div className="tick-head">
              <div className="coin"><b>{s}</b><small>{NAMES[s] || s}</small></div>
              {typeof ch === "number" && (
                <em className={`chip ${ch >= 0 ? "up" : "down"}`}>{ch >= 0 ? "▲" : "▼"} {Math.abs(ch).toFixed(2)}% <small>24ч</small></em>
              )}
            </div>
            <div className="price">{d ? `$${d.price_usd.toLocaleString("en-US", { maximumFractionDigits: d.price_usd < 1 ? 4 : 2 })}` : "—"}</div>
            <Sparkline prices={series} up={trendUp} id={s} />
            <div className="tick-foot">
              <span>7 дней</span>
              {week !== null && <span className={week >= 0 ? "up" : "down"}>{week >= 0 ? "+" : ""}{week.toFixed(2)}%</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
