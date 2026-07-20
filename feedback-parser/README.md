# Feedback Parser — messy client notes → clean revision checklist

Open the page, paste everything the client sent (email chains, Frame.io
comments, texts — all mixed together is fine), pick the revision round, and
get a checklist:

- grouped by **audio / visual / graphics / pacing / story**
- each item with a normalized **MM:SS timecode** ("at about a minute and a
  half" → `01:30`, Frame.io's `00:01:23:04` → `01:23`), the rewritten
  instruction, the client's original words, and a checkbox
- a separate **"Needs clarification"** section for vague or conflicting notes
  ("make it pop"), each with a ready-to-send question — asking these up front
  saves a whole revision round
- **Copy as Markdown** and a print-friendly layout
- a **Round 1/2/3** banner, because three rounds is the deal

Only the text you paste is sent to the AI. It never invents timecodes — a note
with no time reference shows `—`.

## Setup (editor, local file mode)

1. Keep this folder anywhere on your computer.
2. Copy `config.example.js` to a file named exactly **`config.js`** (same
   folder) and paste the API key John gave you into the `apiKey: ""` line.
3. Double-click **`feedback-parser.html`** — it opens in your browser. Done.
   Bookmark it.

If the page says "Not configured yet", step 2 didn't happen or the file is
named `config.js.txt` (Windows hides extensions — turn on "File name
extensions" in Explorer's View menu).

## Setup (John, hosted mode — recommended long term)

1. `cd feedback-parser/vercel-proxy && npx vercel --prod`
2. In the Vercel project settings, add the environment variable
   `ANTHROPIC_API_KEY`.
3. Host `feedback-parser.html` anywhere (Vercel same project works) with a
   `config.js` next to it containing only:

   ```js
   window.FEEDBACK_PARSER_CONFIG = { proxyUrl: "https://<deployment>.vercel.app/api/parse" };
   ```

   No key ever reaches the browser.

## Tips

- Frame.io: select comments → export/copy → paste. The parser recognizes the
  timecoded lines. (If you can export CSV from Frame.io, pasting the CSV text
  works too.)
- Feedback from multiple stakeholders? Paste it all — conflicting notes get
  flagged in "Needs clarification" instead of silently picking a side.
- The checkboxes are for working through the edit; print or copy-as-Markdown
  if you want to save the state (the page itself doesn't save).

## When it breaks

| Message | Fix |
|---|---|
| `Not configured yet` | Create `config.js` as described above and reload. |
| `The API key was rejected` | Key typo, or it was rotated — ask John. |
| `Rate limited` | Wait a minute, try again. |
| Blank page / no styling | You may have opened `config.example.js` or moved the html out of the folder alone. Keep the folder together. |
