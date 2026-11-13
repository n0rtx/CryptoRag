/**
 * Send a question to the RAG backend.
 * @param {string} question - The user's question.
 * @returns {Promise<object>} Answer payload with text, sources and metadata.
 * @throws {Error} If the server responds with an error status.
 */
export async function ask(question) {
  const r = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.answer || "Ошибка сервера");
  return data;
}

/**
 * Fetch cached prices and 7-day charts for all tracked coins.
 * @returns {Promise<{updated: string|null, refresh_seconds: number, coins: object[]}|null>} Market overview, or null if the request failed.
 */
export async function getMarket() {
  const r = await fetch("/api/market");
  if (!r.ok) return null;
  return r.json();
}
