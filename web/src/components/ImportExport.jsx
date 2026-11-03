import { useEffect, useState } from "react";
import { api } from "../lib/api.js";

// Deck import / export. Supports JSON, CSV, and Markdown formats.
// Teaching/learning feature: move decks between instances, share with students.
export default function ImportExport() {
  const [cards, setCards] = useState([]);
  const [format, setFormat] = useState("json");
  const [exportContent, setExportContent] = useState("");
  const [exportFormat, setExportFormat] = useState("json");
  const [importText, setImportText] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.listCards().then(setCards).catch(() => {});
  }, []);

  async function doExport() {
    try {
      const r = await api.exportCards(exportFormat);
      setExportContent(r.content);
    } catch (e) {
      setMsg("Export failed: " + e.message);
    }
  }

  async function doImport() {
    try {
      const parsed = JSON.parse(importText);
      const r = await api.importCards(parsed);
      setMsg(`Imported ${r.added} cards.`);
      setImportText("");
    } catch (e) {
      setMsg("Import failed: " + e.message);
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <h2 className="nomargin">📤 Export deck</h2>
        <p className="muted small nomargin">
          Export your flashcards to share or back up. {cards.length} cards in deck.
        </p>
        <div className="row gap" style={{ marginBottom: "12px" }}>
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value)}
          >
            <option value="json">JSON</option>
            <option value="csv">CSV (Anki-compatible)</option>
            <option value="markdown">Markdown</option>
          </select>
          <button className="primary" onClick={doExport}>Export</button>
        </div>
        {exportContent && (
          <div className="game-prompt">
            <pre>{exportContent}</pre>
          </div>
        )}
        {msg && <p className="muted small">{msg}</p>}
      </div>

      <div className="card">
        <h2 className="nomargin">📥 Import deck</h2>
        <p className="muted small nomargin">
          Paste a JSON array of cards. Each: <code>{"{ front, back, kind, deck, tags }"}</code>.
        </p>
        <textarea
          className="grow"
          rows={6}
          placeholder='[{"front":"What is SQL injection?","back":"...","kind":"flashcard","deck":"web","tags":["sqli","web"]}]'
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
        />
        <div className="row gap" style={{ marginTop: "10px" }}>
          <button className="primary" onClick={doImport}>Import cards</button>
        </div>
      </div>
    </div>
  );
}
