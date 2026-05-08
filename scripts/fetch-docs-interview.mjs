import { spawnSync } from "child_process";
import { writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, "../docs/meetings/raw");

const DOC_IDS = [
  "1eqRXwuRW3bsd1xSiftwRp4sFTuXnc0vWA1WCHqW_FWc",
  "1-c7197pNzqsgqUcoLoTU9vLkQ66MWYEXceydf0t9Ch8",
];

function extractText(doc) {
  const lines = [];
  for (const el of doc.body?.content ?? []) {
    if (!el.paragraph) continue;
    const style = el.paragraph.paragraphStyle?.namedStyleType ?? "";
    const text = (el.paragraph.elements ?? [])
      .map((e) => e.textRun?.content ?? "")
      .join("")
      .replace(/\n$/, "");
    if (!text.trim()) { lines.push(""); continue; }
    if (style === "HEADING_1") lines.push(`# ${text}`);
    else if (style === "HEADING_2") lines.push(`## ${text}`);
    else if (style === "HEADING_3") lines.push(`### ${text}`);
    else lines.push(text);
  }
  return lines.join("\n");
}

import { mkdirSync } from "fs";
mkdirSync(OUT_DIR, { recursive: true });

for (const docId of DOC_IDS) {
  console.log(`Fetching ${docId}...`);
  const result = spawnSync(
    "cmd",
    ["/c", "gws", "docs", "documents", "get", "--params", JSON.stringify({ documentId: docId }), "--format", "json"],
    { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 }
  );
  if (result.error || result.status !== 0) {
    console.error("ERROR:", result.error?.message ?? result.stderr);
    continue;
  }
  const doc = JSON.parse(result.stdout);
  const title = (doc.title ?? docId).replace(/[/\\:*?"<>|]/g, "-").replace(/\s+/g, "_").slice(0, 60);
  writeFileSync(join(OUT_DIR, `${title}.json`), JSON.stringify(doc, null, 2), "utf8");
  writeFileSync(join(OUT_DIR, `${title}.md`), extractText(doc), "utf8");
  console.log(`Saved: ${title}.json / .md`);
}
