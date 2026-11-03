"use client";

// DecisionApproval — blok PERSETUJUAN halaman Decision & Evidence (TAHAP 2,
// 29 Okt 2026, gaya clean dashboard).
//
// Bentuk yang dituju: satu kartu rapat yang menjawab tiga hal berurutan —
//   (1) APA yang menahan (kalimat dari server, bukan enum),
//   (2) SIAPA yang dibutuhkan sekarang (nama peran, bukan kode),
//   (3) APA yang terjadi setelah langkah ini,
// lalu SATU tabel penyetuju (peran · keadaan · dicatat) dan SATU tombol aksi
// (popup yang sudah ada, `DecisionActions`) — bukan deretan tombol.
//
// Yang TIDAK dilakukan komponen ini: menghitung status persetujuan sendiri.
// Semua kalimat dan baris diambil dari `lib/approval-panel` dan `lib/governance`
// yang sudah dipakai panel lain, supaya satu keputusan tidak punya dua versi
// kebenaran. Kalau ringkasan belum tiba, komponen menulis keadaannya — tidak
// menyimpulkan "tidak ada persetujuan".

import DecisionActions from "./DecisionActions";
import { ledgerPenyetuju, tigaJawaban } from "../lib/approval-panel";
import { statusLabel } from "../lib/bahasa";
import { governanceView } from "../lib/governance";

export default function DecisionApproval({
  decisionId,
  role,
  status,
  token,
  summary,
  now,
}: {
  decisionId: string;
  role: string;
  status: string | null | undefined;
  token: string | null;
  summary: unknown;
  now: Date | null;
}) {
  const adaRingkasan = summary !== null && summary !== undefined;
  const jawaban = adaRingkasan ? tigaJawaban({ summary, role, now }) : null;
  const baris = adaRingkasan ? ledgerPenyetuju({ summary, now }) : [];
  const label = statusLabel(status);
  const view = governanceView(summary);
  // Kalimat "tidak ada yang menahan" hanya boleh muncul saat memang TIDAK ADA
  // yang kurang. Sebab tertulis datang dari `blocking_reasons` milik server;
  // bila server tidak mengirimkannya padahal peran masih kurang, menulis
  // "tidak ada yang menahan" adalah klaim yang salah — jadi dipisah tiga arah.
  const tanpaPenahan =
    view.state === "siap" || view.state === "lengkap" || view.state === "selesai";

  return (
    <article className="approval-block" id="zona-keputusan" data-bagian="keputusan">
      <div className="approval-head">
        <h2>Persetujuan</h2>
        <div className="approval-head-right">
          {label ? (
            <span className="evidence-header-status" data-status={String(status ?? "")}>
              {label}
            </span>
          ) : null}
          {/* Satu pemicu aksi: seluruh pilihan (setujui/tolak/eksekusi/PO)
              hidup di popup yang sudah ada, lengkap dengan galatnya. */}
          <DecisionActions
            key={decisionId}
            decisionId={decisionId}
            role={role}
            status={status ?? ""}
            token={token}
            summary={summary}
            izinPersetujuan={false}
          />
        </div>
      </div>

      {!adaRingkasan ? (
        <p className="approval-note" role="status" data-testid="persetujuan-menunggu">
          Ringkasan persetujuan sedang dimuat. Status keputusan di atas tetap
          berasal dari data keputusan, bukan dari blok ini.
        </p>
      ) : (
        <>
          {jawaban && jawaban.menahan.length > 0 ? (
            <div className="approval-blocker" data-tone="warn">
              <p className="approval-blocker-title">Yang menahan</p>
              <ul className="approval-blocker-list">
                {jawaban.menahan.map((sebab) => (
                  <li key={sebab}>{sebab}</li>
                ))}
              </ul>
            </div>
          ) : tanpaPenahan ? (
            <p className="approval-clear" data-testid="tanpa-penahan">
              Tidak ada yang menahan persetujuan keputusan ini.
            </p>
          ) : (
            <p className="approval-note" data-testid="tanpa-sebab-tertulis">
              Tidak ada sebab tertulis dari server untuk keputusan ini; peran yang
              masih kurang tercantum di baris Dibutuhkan.
            </p>
          )}

          {/* Dua jawaban sisanya dibuat sebagai baris label–nilai rapat, bukan
              paragraf: pembaca memindai labelnya, bukan kalimatnya. */}
          {jawaban ? (
            <dl className="approval-facts">
              <div className="approval-fact">
                <dt>Dibutuhkan</dt>
                <dd>{jawaban.dibutuhkan}</dd>
              </div>
              <div className="approval-fact">
                <dt>Setelah ini</dt>
                <dd>{jawaban.setelah}</dd>
              </div>
            </dl>
          ) : null}

          {baris.length > 0 ? (
            <table className="approval-roles">
              <caption className="approval-roles-caption">
                Peran yang disyaratkan
              </caption>
              <thead>
                <tr>
                  <th scope="col">Peran</th>
                  <th scope="col">Keadaan</th>
                  <th scope="col">Dicatat</th>
                </tr>
              </thead>
              <tbody>
                {baris.map((item) => (
                  <tr key={item.roles.join("+")} data-done={item.done ? "ya" : "belum"}>
                    <th scope="row">
                      {item.label}
                      {item.catatan ? (
                        <span className="approval-role-note" title={item.catatan}>
                          {item.catatan}
                        </span>
                      ) : null}
                    </th>
                    <td>{item.done ? "Sudah menyetujui" : "Menunggu"}</td>
                    <td className="approval-role-waktu">
                      {item.done ? [item.nama, item.jam].filter(Boolean).join(" · ") || "—" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="approval-note">
              Belum ada baris persetujuan untuk keputusan ini.
            </p>
          )}
        </>
      )}
    </article>
  );
}
