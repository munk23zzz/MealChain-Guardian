// Ekstrak sourcesContent dari inline sourcemap bundle SSR (TS asli!).
// Jalankan dari repo root: node scripts/recover_sourcemap.cjs
const fs = require("fs");
const path = require("path");
const tmp = process.env.LOCALAPPDATA || "C:\\Users\\User\\AppData\\Local";
const s = fs.readFileSync(path.join(tmp, "Temp", "page_ssr.js"), "utf8");

const re = /sourceMappingURL=data:application\/json;charset=utf-8;base64,([A-Za-z0-9+/=]+)/g;
let m, n = 0;
while ((m = re.exec(s)) !== null) {
  n++;
  try {
    const json = Buffer.from(m[1], "base64").toString("utf8");
    const map = JSON.parse(json);
    const srcs = (map.sources || []).map((x) => String(x));
    if (!srcs.some((x) => x.includes("lib/api"))) continue;
    const idx = srcs.findIndex((x) => x.includes("lib/api"));
    const contents = map.sourcesContent || [];
    if (contents[idx]) {
      const out = path.join(tmp, "Temp", "api_original.ts");
      fs.writeFileSync(out, contents[idx]);
      console.log(`MAP#${n}: FOUND sourcesContent for lib/api.ts -> ${out}`);
      console.log("bytes:", contents[idx].length);
      console.log("Bearer:", (contents[idx].match(/Bearer/g) || []).length);
      console.log("has types:", /token:\s*string/.test(contents[idx]));
    } else {
      console.log(`MAP#${n}: has lib/api source but NO sourcesContent`);
    }
  } catch (e) {
    console.log(`MAP#${n}: parse fail:`, e.message);
  }
}
console.log("total maps:", n);
