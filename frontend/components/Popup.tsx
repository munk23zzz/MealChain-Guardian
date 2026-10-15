"use client";

// Popup — cangkang dialog modal yang dipakai ulang (permintaan Roy
// 2026-10-14: menu approval dipindah dari dalam kartu ke jendela popup).
// Yang dijaga di sini bukan hiasan, tapi perilaku:
// - `role="dialog"` + `aria-modal` + `aria-labelledby` → pembaca layar tahu
//   konteksnya, dan halaman di belakangnya tidak dibacakan sebagai aktif;
// - Escape dan klik latar menutup; fokus dipindah ke kontrol pertama saat
//   dibuka, dan DIKEMBALIKAN ke tombol pemicu saat ditutup (kalau tidak,
//   pengguna keyboard kembali ke awal dokumen);
// - Tab berputar di dalam popup, tidak bocor ke halaman di belakangnya;
// - gulir latar dikunci supaya tidak ada dua gulir yang berebut;
// - dirender lewat portal ke <body>: kartu-kartu di konsol ini hidup di dalam
//   grid ber-overflow, dan popup yang tinggal di sana akan terpotong;
// - animasi memakai token --dur-* dan dimatikan oleh prefers-reduced-motion
//   (lihat blok .popup-* di app/globals.css).

import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'a[href], area[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])';

export default function Popup({
  open,
  onClose,
  title,
  description,
  labelledBy = "popup-title",
  returnFocusRef,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  /** id elemen judul — dipakai aria-labelledby (harus unik per popup). */
  labelledBy?: string;
  /**
   * Elemen yang menerima fokus kembali saat popup ditutup. Disarankan diisi
   * dengan ref tombol pemicu: peramban yang TIDAK memfokuskan tombol saat
   * diklik (mis. Safari) tidak akan memulihkan fokus ke tempat yang benar
   * kalau kita hanya mengandalkan document.activeElement.
   */
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const fallbackFocusRef = useRef<HTMLElement | null>(null);
  // onClose disimpan di ref: kalau ia masuk daftar dependensi, setiap render
  // induk akan menjalankan ulang effect — fokus pemanggil ikut dipulihkan di
  // tengah penggunaan.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const node = dialogRef.current;
    fallbackFocusRef.current = (document.activeElement as HTMLElement | null) ?? null;
    // Dibaca SEKARANG, bukan di cleanup: ref bisa berubah sebelum cleanup jalan
    // (peringatan react-hooks/exhaustive-deps), dan pemicunya sudah ada saat
    // popup dibuka.
    const returnTarget = returnFocusRef?.current ?? null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const first = node?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? node)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (items.length === 0) {
        event.preventDefault();
        node.focus();
        return;
      }
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault();
        lastEl.focus();
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault();
        firstEl.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      // Kembalikan fokus ke pemicu (ref eksplisit lebih dipercaya daripada
      // activeElement yang bergantung perilaku fokus peramban).
      (returnTarget ?? fallbackFocusRef.current)?.focus?.();
    };
  }, [open, returnFocusRef]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="popup-backdrop"
      // mousedown, bukan click: klik yang MULAI di dalam popup (mis. seleksi
      // teks di textarea) lalu lepas di latar tidak boleh menutup jendela.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeRef.current();
      }}
    >
      <div
        className="popup"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={description ? `${labelledBy}-desc` : undefined}
        ref={dialogRef}
        tabIndex={-1}
      >
        <header className="popup-head">
          <div className="popup-heading">
            <h3 className="popup-title" id={labelledBy}>
              {title}
            </h3>
          </div>
          <button
            type="button"
            className="popup-close"
            onClick={() => closeRef.current()}
            aria-label="Tutup jendela"
            title="Tutup (Esc)"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
              <path
                d="M3.5 3.5l9 9M12.5 3.5l-9 9"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>
        {description ? (
          <p className="popup-desc" id={`${labelledBy}-desc`}>
            {description}
          </p>
        ) : null}
        <div className="popup-body">{children}</div>
      </div>
    </div>,
    document.body
  );
}
