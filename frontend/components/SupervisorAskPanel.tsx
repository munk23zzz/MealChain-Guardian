"use client";

// SupervisorAskPanel — tanya-jawab baca-saja (dokumen 06 §2.9).
//
// Hanya dirender untuk peran non-approver. Jalurnya `POST /agent/supervisor/ask`
// yang dijawab tool GET: tidak menulis keputusan, trace, atau blok ledger.
// Setiap jawaban menampilkan asalnya (mode + tool + "tidak menulis apa pun")
// supaya tidak terbaca sebagai aksi.

import { useState } from "react";

import { askSupervisor } from "../lib/api";
import { askProvenance, type AskAnswer } from "../lib/agent-activity";

const CONTOH = [
  "Berapa keputusan yang menunggu persetujuan?",
  "Bagaimana status rantai ledger?",
  "Apa keputusan terbaru?",
  "Model supervisor apa yang terkonfigurasi?",
];

export default function SupervisorAskPanel({ token }: { token: string | null }) {
  const [tanya, setTanya] = useState("");
  const [jawab, setJawab] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [memuat, setMemuat] = useState(false);

  async function kirim(pertanyaan: string) {
    const bersih = pertanyaan.trim();
    if (!bersih || !token) return;
    setMemuat(true);
    setError(null);
    try {
      const hasil = (await askSupervisor(bersih, token)) as AskAnswer;
      setJawab(hasil);
    } catch (e) {
      setJawab(null);
      setError(
        e instanceof Error ? e.message : "Pertanyaan gagal dijawab backend."
      );
    } finally {
      setMemuat(false);
    }
  }

  return (
    <section className="aa-ask" aria-labelledby="aa-ask-title">
      <h3 id="aa-ask-title" className="aa-section-title">
        Tanya supervisor
      </h3>
      <p className="aa-ask-note">
        Dijawab dari tool baca-saja. Tidak ada keputusan, trace, atau blok ledger
        yang ditulis oleh pertanyaan ini.
      </p>

      <form
        className="aa-ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          void kirim(tanya);
        }}
      >
        <label className="aa-ask-field">
          <span className="aa-sr">Pertanyaan untuk supervisor</span>
          <input
            type="text"
            className="aa-ask-input"
            value={tanya}
            placeholder="Contoh: berapa keputusan yang menunggu persetujuan?"
            onChange={(e) => setTanya(e.target.value)}
            maxLength={400}
          />
        </label>
        <button
          type="submit"
          className="aa-ask-btn"
          disabled={memuat || !tanya.trim() || !token}
        >
          {memuat ? "Menjawab…" : "Tanya"}
        </button>
      </form>

      <ul className="aa-ask-contoh">
        {CONTOH.map((c) => (
          <li key={c}>
            <button
              type="button"
              className="aa-ask-chip"
              onClick={() => {
                setTanya(c);
                void kirim(c);
              }}
            >
              {c}
            </button>
          </li>
        ))}
      </ul>

      {error ? (
        <p className="aa-ask-error" role="alert">
          {error}
        </p>
      ) : null}

      {jawab ? (
        <div className="aa-ask-answer" role="status">
          <p className="aa-ask-text">{jawab.answer ?? "Jawaban kosong."}</p>
          <p className="aa-ask-source">{askProvenance(jawab)}</p>
        </div>
      ) : null}
    </section>
  );
}
