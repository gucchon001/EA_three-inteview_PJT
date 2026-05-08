/**
 * docs/samples/monthly-reports の配布用 HTML を
 * src/reports/templates/monthly-reports/ へ同期する（Vercel @vercel/static）。
 *
 * - ルートの *_report.html（最新）
 * - reports-manifest.json（エディタのサンプル URL・revision 正本）
 * - tools/（社内向け全文エディタ等、あれば）
 * - SECURE_DELIVERY_月次レポート_HTML.md（配布時のセキュリティ手順、あれば）
 * - versions/ 以下（v1 凍結・v2 凍結・README）を再帰コピー
 *
 * 正本は docs 側。デプロイ前: node scripts/sync_monthly_reports_to_vercel.mjs
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const srcBase = join(root, "docs", "samples", "monthly-reports");
const destBase = join(root, "src", "reports", "templates", "monthly-reports");

function copyDirRecursive(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const name of readdirSync(src)) {
    const s = join(src, name);
    const d = join(dest, name);
    if (statSync(s).isDirectory()) copyDirRecursive(s, d);
    else copyFileSync(s, d);
  }
}

mkdirSync(destBase, { recursive: true });

const reportHtml = readdirSync(srcBase).filter((n) => n.endsWith("_report.html"));
if (reportHtml.length === 0) {
  console.warn("no *_report.html in", srcBase);
  process.exit(1);
}
for (const name of reportHtml) {
  copyFileSync(join(srcBase, name), join(destBase, name));
  console.log("copied", name);
}

const versionsSrc = join(srcBase, "versions");
const versionsDest = join(destBase, "versions");
try {
  if (statSync(versionsSrc).isDirectory()) {
    copyDirRecursive(versionsSrc, versionsDest);
    console.log("copied versions/ →", versionsDest);
  }
} catch {
  console.warn("no versions/ folder, skip");
}

const hubSrc = join(srcBase, "monthly-reports-index.html");
if (existsSync(hubSrc)) {
  copyFileSync(hubSrc, join(destBase, "index.html"));
  console.log("copied monthly-reports-index.html -> index.html");
}

const manifestSrc = join(srcBase, "reports-manifest.json");
if (existsSync(manifestSrc)) {
  copyFileSync(manifestSrc, join(destBase, "reports-manifest.json"));
  console.log("copied reports-manifest.json");
} else {
  console.warn("reports-manifest.json not found, skip");
}

const toolsSrc = join(srcBase, "tools");
try {
  if (existsSync(toolsSrc) && statSync(toolsSrc).isDirectory()) {
    copyDirRecursive(toolsSrc, join(destBase, "tools"));
    console.log("copied tools/ →", join(destBase, "tools"));
  }
} catch {
  console.warn("no tools/ folder, skip");
}

const secureName = "SECURE_DELIVERY_月次レポート_HTML.md";
const secureSrc = join(srcBase, secureName);
if (existsSync(secureSrc)) {
  copyFileSync(secureSrc, join(destBase, secureName));
  console.log("copied", secureName);
}
