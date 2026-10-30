// Ukur terminal "Proses pengambilan data" (Demo Control) pada lebar sempit.
// Sementara/alat QA — bukan bagian aplikasi, tidak diimpor siapa pun.
//   NODE_PATH=<repo>/frontend/node_modules UKUR_LEBAR=390 UKUR_AKUN="SPPG Head" \
//     UKUR_TUNGGU=14000 node _qa/ukur-terminal.cjs
// Butuh: Edge + `ws` dari frontend/node_modules. Kredensial tidak dibaca di sini:
// akun demo diisi oleh server lewat tombol akun, sama seperti `ukur-viewport.cjs`.
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const WebSocket = require("ws");

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9335;
const PROFILE = (process.env.TMPDIR || ".") + "/edge-ukur-terminal";
const LEBAR = Number(process.env.UKUR_LEBAR || 390);
const AKUN = process.env.UKUR_AKUN || "SPPG Head";
const TUNGGU = Number(process.env.UKUR_TUNGGU || 14000);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(path) {
  return new Promise((resolve, reject) => {
    const req = http.get({ host: "127.0.0.1", port: PORT, path }, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    });
    req.on("error", reject);
  });
}

async function main() {
  fs.rmSync(PROFILE, { recursive: true, force: true });
  const browser = spawn(
    EDGE,
    [
      "--headless=new",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${PROFILE}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--window-size=1280,900",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  let version = null;
  for (let i = 0; i < 60; i += 1) {
    try {
      version = await httpJson("/json/version");
      break;
    } catch (e) {
      await sleep(250);
    }
  }
  if (!version) throw new Error("Edge tidak membuka port debug");

  let target = null;
  for (let i = 0; i < 40; i += 1) {
    const list = await httpJson("/json/list");
    target = list.find((t) => t.type === "page");
    if (target) break;
    await sleep(250);
  }
  if (!target) throw new Error("tidak ada target page");

  const ws = new WebSocket(target.webSocketDebuggerUrl, { perMessageDeflate: false });
  const pending = new Map();
  let seq = 0;
  ws.on("message", (raw) => {
    const msg = JSON.parse(raw);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  });
  await new Promise((r) => ws.on("open", r));

  const send = (method, params = {}) =>
    new Promise((resolve) => {
      const id = ++seq;
      pending.set(id, resolve);
      ws.send(JSON.stringify({ id, method, params }));
    });

  const evaluate = async (expression) => {
    const res = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (res.result && res.result.exceptionDetails) {
      throw new Error("eval: " + JSON.stringify(res.result.exceptionDetails.text));
    }
    return res.result && res.result.result ? res.result.result.value : undefined;
  };

  const waitFor = async (expr, label, limit = 80) => {
    for (let i = 0; i < limit; i += 1) {
      if (await evaluate(`Boolean(${expr})`)) return true;
      await sleep(500);
    }
    throw new Error("waktu habis menunggu: " + label);
  };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: LEBAR,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true,
  });
  await send("Page.navigate", { url: "http://localhost:3010" });

  await waitFor("document.querySelector('input[type=\"email\"]')", "layar masuk");
  await waitFor("document.querySelector('.demo-link')", "tautan akun demo");
  await sleep(2000);
  let terisi = false;
  for (let i = 0; i < 8 && !terisi; i += 1) {
    await evaluate(
      `(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === ${JSON.stringify(AKUN)}); if (b) b.click(); return true; })()`,
    );
    await sleep(700);
    terisi = Boolean(await evaluate("(document.querySelector('input[type=\"email\"]')||{}).value"));
  }
  if (!terisi) throw new Error("akun demo tidak mengisi form");
  await evaluate(
    `(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Masuk'); b.click(); return true; })()`,
  );
  await waitFor("document.querySelector('nav button')", "konsol setelah masuk");

  await evaluate(
    `(() => { const b = [...document.querySelectorAll('nav button')].find((x) => /Demo Control/.test(x.textContent)); b.click(); return true; })()`,
  );
  await sleep(3000);
  const diklik = await evaluate(
    `(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Jalankan agent'); if (!b) return false; b.click(); return true; })()`,
  );
  if (!diklik) throw new Error("tombol Jalankan agent tidak ada");
  await sleep(TUNGGU);

  const hasil = await evaluate(`(() => {
    const term = document.querySelector('.dc-term');
    const badan = document.querySelector('.dc-term-badan');
    const baris = document.querySelector('.dc-term-baris');
    const jam = document.querySelector('.dc-term-jam');
    const isi = document.querySelector('.dc-term-isi');
    const langkah = document.querySelector('.dc-term-langkah');
    const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { w: Math.round(b.width), h: Math.round(b.height) }; };
    return {
      lebarViewport: window.innerWidth,
      docScrollWidth: document.documentElement.scrollWidth,
      docClientWidth: document.documentElement.clientWidth,
      adaGulirHorizontalHalaman: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      terminal: r(term),
      badan: badan ? { ...r(badan), clientH: badan.clientHeight, scrollH: badan.scrollHeight, overflowY: getComputedStyle(badan).overflowY } : null,
      baris: r(baris),
      jumlahBaris: document.querySelectorAll('.dc-term-baris').length,
      kolomBaris: baris ? getComputedStyle(baris).gridTemplateColumns : null,
      jamFont: jam ? getComputedStyle(jam).fontFamily : null,
      jamUkuran: jam ? getComputedStyle(jam).fontSize : null,
      langkahBerat: langkah ? getComputedStyle(langkah).fontWeight : null,
      isiWrap: isi ? getComputedStyle(isi).overflowWrap : null,
      pil: document.querySelector('.dc-term-pil')?.textContent ?? null,
      tinggiHalaman: document.documentElement.scrollHeight,
    };
  })()`);
  if (!hasil.terminal) {
    hasil.diagnosa = await evaluate(
      `(() => ({
        blok: (document.querySelector('[aria-label="Jalankan agent"]')?.innerText || '').slice(0, 400),
        galat: document.querySelector('.dc-error')?.textContent ?? null,
        progres: document.querySelector('.dc-progress')?.textContent ?? null,
        tombol: [...document.querySelectorAll('button')].map((b) => b.textContent.trim()).filter((t) => /Jalankan|agent/i.test(t)),
      }))()`,
    );
  }
  console.log(JSON.stringify(hasil, null, 1));
  ws.close();
  browser.kill();
}

main().catch((e) => {
  console.error("GAGAL:", e.message);
  process.exit(1);
});
