// Loading and reading the two data files: data/status.json and data/history.csv.

const TRUE_FALSE = ["in_role", "first_run"];

// Split CSV text into rows of cells. Handles quoted cells ("a, b" and "" for a quote).
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// history.csv text -> array of posting objects. in_role and first_run become true/false.
export function parseHistory(text) {
  const [header, ...body] = parseCsv(text);
  return body.map((cells) => {
    const row = {};
    header.forEach((name, i) => {
      const value = cells[i] ?? "";
      row[name] = TRUE_FALSE.includes(name) ? value === "true" : value;
    });
    return row;
  });
}

async function fetchText(path) {
  // "no-cache" = ask the network whether the file changed. Offline, the service worker
  // answers with the last copy it saved.
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.text();
}

export async function loadData() {
  const [statusText, historyText] = await Promise.all([fetchText("data/status.json"), fetchText("data/history.csv")]);
  return { status: JSON.parse(statusText), rows: parseHistory(historyText) };
}
