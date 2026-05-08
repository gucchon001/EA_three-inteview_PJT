import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const sheetId = "1hDvy9jHp1KcRWgxYgPlrRO3XkdJtB3nQSynIrHlANVA";
const docId = "13biNdCru3hg9VIqUn20WMpNQHn6S_6XGRnIHcAFEStU";
const root = "c:/dev/CODE/EA_three-inteview_PJT/data";

/** Windows: spawn .cmd causes EINVAL; call global CLI entry with node instead. */
function gwsSpawnArgs(argv) {
  if (process.platform === "win32") {
    const runGws = join(homedir(), "AppData", "Roaming", "npm", "node_modules", "@googleworkspace", "cli", "run-gws.js");
    return { cmd: process.execPath, args: [runGws, ...argv] };
  }
  return { cmd: "gws", args: argv };
}

function gws(argv) {
  const { cmd, args } = gwsSpawnArgs(argv);
  const r = spawnSync(cmd, args, {
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    env: process.env,
  });
  if (r.error) throw r.error;
  if (r.status !== 0) {
    throw new Error(
      `gws exit ${r.status} signal ${r.signal}\nstderr:${r.stderr}\nstdout:${(r.stdout || "").slice(0, 800)}`,
    );
  }
  return r.stdout;
}

function valuesGet(spreadsheetId, sheetTitle, a1Suffix = "A1:Z200") {
  const range = /[\s'"]/.test(sheetTitle)
    ? `'${sheetTitle.replace(/'/g, "''")}'!${a1Suffix}`
    : `${sheetTitle}!${a1Suffix}`;
  return gws([
    "sheets",
    "spreadsheets",
    "values",
    "get",
    "--params",
    JSON.stringify({ spreadsheetId, range }),
  ]);
}

const meta = gws(["sheets", "spreadsheets", "get", "--params", JSON.stringify({ spreadsheetId: sheetId })]);
writeFileSync(`${root}/_student2_sheet_meta.json`, meta, "utf8");
const metaObj = JSON.parse(meta);
const sheets = (metaObj.sheets || []).map((s) => ({
  sheetId: s.properties.sheetId,
  title: s.properties.title,
}));
console.log("sheets:", JSON.stringify(sheets, null, 2));

const studentTitle = sheets.find((s) => s.title === "student")?.title;
const lessonTitle = sheets.find((s) => s.title === "lesson plan")?.title;
if (!studentTitle) throw new Error('no sheet titled "student"');
if (!lessonTitle) throw new Error('no sheet titled "lesson plan"');

writeFileSync(
  `${root}/_student2_student_values.json`,
  valuesGet(sheetId, studentTitle),
  "utf8",
);
console.log("student values OK:", studentTitle);

writeFileSync(
  `${root}/_student2_lesson_values.json`,
  valuesGet(sheetId, lessonTitle),
  "utf8",
);
console.log("lesson plan values OK:", lessonTitle);

const doc = gws(["docs", "documents", "get", "--params", JSON.stringify({ documentId: docId }), "--format", "json"]);
writeFileSync(`${root}/_student2_mtg_doc.json`, doc, "utf8");
console.log("doc bytes:", doc.length);
