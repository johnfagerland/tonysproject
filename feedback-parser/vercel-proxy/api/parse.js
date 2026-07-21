// Tiny serverless proxy so the hosted version of feedback-parser.html never
// ships an API key to the browser. Deploy this folder to Vercel and set the
// ANTHROPIC_API_KEY environment variable in the Vercel project settings.
//
//   cd feedback-parser/vercel-proxy && npx vercel --prod
//
// Then set proxyUrl in config.js (or bake it into the hosted page's config.js)
// to https://<your-deployment>.vercel.app/api/parse

export default async function handler(req, res) {
  // Same-origin page or the local file:// page may call this; keep CORS open —
  // the key stays server-side either way and this endpoint only relays to one API.
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "content-type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: { message: "POST only" } });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: { message: "Server not configured (missing ANTHROPIC_API_KEY)" } });
  }

  // Relay only the fields the page actually uses — this proxy is not a
  // general-purpose API gateway.
  const { model, max_tokens, output_config, messages } = req.body || {};
  const upstream = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: model || "claude-opus-4-8",
      max_tokens: Math.min(max_tokens || 8000, 16000),
      output_config,
      messages,
    }),
  });

  const data = await upstream.json();
  return res.status(upstream.status).json(data);
}
