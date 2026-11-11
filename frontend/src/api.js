// Относительные URL: фронт и API живут на одном домене (Flask раздаёт и то, и другое)
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

export async function getPrice(symbol) {
  const r = await fetch(`/api/price/${symbol}`);
  if (!r.ok) return null;
  return r.json();
}

export async function getChart(symbol, days = 7) {
  const r = await fetch(`/api/chart/${symbol}?days=${days}`);
  if (!r.ok) return null;
  return (await r.json()).prices;
}
