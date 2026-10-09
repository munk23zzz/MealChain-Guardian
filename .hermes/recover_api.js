// Recovery api.ts dari webpack SSR bundle (eval string deobfuscate).
const fs = require("fs");
const path = require("path");
const tmp = process.env.LOCALAPPDATA || "C:\\Users\\User\\AppData\\Local";
const s = fs.readFileSync(path.join(tmp, "Temp", "page_ssr.js"), "utf8");

const mod = s.indexOf('(ssr)/./lib/api.ts');
// definisi modul webpack: "(ssr)/./lib/api.ts":\n/*! ... */\n/***/ ((__unused_webpack_module...
const defIdx = s.indexOf('(ssr)/./lib/api.ts":', mod + 10);
const ev = s.indexOf('eval(', defIdx);
if (ev < 0) { console.error("no eval after def", defIdx); process.exit(1); }
// eval("...") — string dimulai pada quote pertama setelah eval(
let i = ev + 5;
while (s[i] !== '"' && s[i] !== "'") i++;
const quote = s[i];
let j = i + 1;
while (true) {
  const k = s.indexOf(quote, j);
  if (k < 0) { console.error("no closing quote"); process.exit(1); }
  let bs = 0, p = k - 1;
  while (s[p] === '\\') { bs++; p--; }
  if (bs % 2 === 0) { j = k; break; }
  j = k + 1;
}
const lit = s.slice(i, j + 1);
const code = JSON.parse(lit); // eval pakai double-quoted JS string == JSON string
fs.writeFileSync(path.join(tmp, "Temp", "api_recovered.js"), code);
const bearer = (code.match(/Bearer/g) || []).length;
const stars = (code.match(/\*\*\*/g) || []).length;
console.log("bytes:", code.length, "Bearer:", bearer, "stars:", stars);
console.log("exports:", (code.match(/^async function \w+/gm) || []).length, "fns");
