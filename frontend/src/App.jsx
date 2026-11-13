import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ask, getMarket } from "./api";
import Market from "./Market.jsx";

const EXAMPLES = [
  "Чем Solana отличается от Ethereum?",
  "Сколько сейчас стоит BTC?",
  "Что такое халвинг биткоина?",
  "How does Ethereum staking work?",
];

/** Sun icon shown in the dark theme. */
const Sun = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </svg>
);
/** Moon icon shown in the light theme. */
const Moon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);

/**
 * Manage the color theme and persist it in localStorage.
 * @returns {[string, Function]} Current theme name and a function that toggles it.
 */
function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "dark");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch (e) {}
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

/**
 * Root component with the chat and market tabs and the theme switch.
 * @returns {JSX.Element} The application.
 */
export default function App() {
  const [tab, setTab] = useState("chat");
  const [theme, toggleTheme] = useTheme();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (tab === "chat") endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, tab]);

  /**
   * Send a question to the backend and append the answer to the conversation.
   * @param {string} text - Question text.
   * @returns {Promise<void>}
   */
  async function send(text) {
    const q = text.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await ask(q);
      setMessages((m) => [...m, { role: "bot", ...res, text: res.answer }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "bot", text: e.message, error: true }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1><span className="logo">₿</span> Crypto<span>RAG</span></h1>
          <p>Вопросы о криптовалютах — по базе знаний и живым данным CoinGecko</p>
        </div>
        <button className="theme-btn" onClick={toggleTheme} aria-label="Сменить тему" title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}>
          {theme === "dark" ? <Sun /> : <Moon />}
        </button>
      </header>

      <nav className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "chat"} className={tab === "chat" ? "on" : ""} onClick={() => setTab("chat")}>Чат</button>
        <button role="tab" aria-selected={tab === "market"} className={tab === "market" ? "on" : ""} onClick={() => setTab("market")}>Рынок</button>
      </nav>

      <section className={`panel ${tab === "market" ? "" : "off"}`}>
        <div className="scroll"><Market getMarket={getMarket} /></div>
      </section>

      <section className={`panel ${tab === "chat" ? "" : "off"}`}>
        <main className="chat scroll">
          {messages.length === 0 && (
            <div className="examples">
              {EXAMPLES.map((e) => (
                <button key={e} onClick={() => send(e)}>{e}</button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role} ${m.blocked ? "blocked" : ""} ${m.error ? "error" : ""}`}>
              <div className="bubble">
                {m.role === "bot" && !m.error ? (
                  <div className="md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (p) => <a {...p} target="_blank" rel="noopener noreferrer" /> }}>{m.text}</ReactMarkdown></div>
                ) : m.text}
              </div>
              {m.sources?.length > 0 && (
                <div className="sources">Источники: {[...new Set(m.sources.map((s) => s.source))].join(", ")}</div>
              )}
              {m.cached && <div className="sources">из кэша</div>}
            </div>
          ))}
          {loading && <div className="msg bot"><div className="bubble typing"><i /><i /><i /></div></div>}
          <div ref={endRef} />
        </main>

        <form onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Например: что такое Proof of History в Solana?"
            maxLength={500}
            autoFocus
          />
          <button disabled={loading || !input.trim()}>Отправить <span>→</span></button>
        </form>
      </section>
    </div>
  );
}
