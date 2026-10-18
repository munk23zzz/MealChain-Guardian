// Preload readlink untuk build di drive exFAT (mis. E: di Windows).
//
// Di exFAT, `fs.readlink()` pada berkas BIASA melempar EISDIR, sedangkan webpack
// (lewat enhanced-resolve) menyimpulkan "ini bukan symlink" hanya bila errornya
// EINVAL. Akibatnya `next build` gagal dengan:
//
//   Error: EISDIR: illegal operation on a directory, readlink
//   '...\node_modules\next\dist\pages\_app.js'
//
// Berkas ini dipakai lewat `node -r ./scripts/exfat-readlink-patch.cjs` pada
// script `build` di package.json. Di NTFS/Linux/macOS patch ini tidak mengubah
// apa pun: readlink di sana memang sudah mengembalikan EINVAL untuk non-symlink.
const fs = require("fs");

function normalisasi(err, path) {
  if (err && err.code === "EISDIR") {
    const e = new Error(`EINVAL: invalid argument, readlink '${path}'`);
    e.code = "EINVAL";
    e.errno = -22;
    e.syscall = "readlink";
    e.path = path;
    return e;
  }
  return err;
}

const readlinkSyncAsli = fs.readlinkSync;
fs.readlinkSync = function (path, ...rest) {
  try {
    return readlinkSyncAsli.call(fs, path, ...rest);
  } catch (err) {
    throw normalisasi(err, path);
  }
};

const readlinkAsli = fs.readlink;
fs.readlink = function (path, ...rest) {
  const cb = rest[rest.length - 1];
  if (typeof cb === "function") {
    return readlinkAsli.call(fs, path, ...rest.slice(0, -1), (err, val) =>
      cb(err ? normalisasi(err, path) : err, val)
    );
  }
  try {
    return readlinkAsli.call(fs, path, ...rest);
  } catch (err) {
    throw normalisasi(err, path);
  }
};

const readlinkPromiseAsli = fs.promises.readlink;
fs.promises.readlink = async function (path, ...rest) {
  try {
    return await readlinkPromiseAsli.call(fs.promises, path, ...rest);
  } catch (err) {
    throw normalisasi(err, path);
  }
};
