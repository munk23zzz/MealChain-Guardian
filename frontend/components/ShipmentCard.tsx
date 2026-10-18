import type { ReactNode } from "react";

import {
  pickShipments,
  shipmentDetails,
  shipmentHeadline,
  shipmentKeyFacts,
  shipmentSafetyChip,
  shipmentSteps,
  shipmentTitle,
  shipmentVerdict,
} from "../lib/shipment-card";
import {
  shipmentKey,
  supplierRoutes,
  type SupplierRoute,
} from "../lib/supplier-routes";
import {
  shipmentEvents,
  shipmentRouteAudit,
  shipmentTimelineLabel,
} from "../lib/shipment-timeline";

/**
 * Kartu "Informasi pengiriman" (Arah A riset 16 Okt 2026).
 *
 * Satu kiriman = satu blok dengan empat lapis informasi, dari yang paling
 * cepat dibaca ke yang paling rinci:
 *   1. judul `Pemasok → Tujuan` + pil status (keadaan + sisa waktu),
 *   2. stepper empat tahap (dipanen → berangkat → di jalan → tiba),
 *   3. satu baris angka kunci (jarak jalan · waktu tempuh · muatan),
 *   4. kalimat keputusan, lalu rincian lengkap di balik panel lipat.
 *
 * Panel rincian memakai `<details>` bawaan peramban: tetap bekerja tanpa
 * JavaScript, isinya tetap ada di DOM saat tertutup, dan tidak perlu keadaan
 * klien — satu alasan yang sama dengan keputusan peta "bisa dimuat tanpa
 * interaksi" sebelumnya.
 *
 * Komponen ini SENGAJA tidak merender apa pun saat tidak ada kiriman aktif —
 * kartu kosong lebih buruk daripada tidak ada kartu. Tab Keamanan Pangan adalah
 * pengecualian yang dinyatakan: di sana "tidak ada kiriman" justru jawaban yang
 * dicari, jadi bisa diminta lewat `empty`.
 */
export default function ShipmentCard({
  routes,
  title = "Informasi pengiriman",
  maks = 3,
  note,
  hanya,
  empty,
  action,
}: {
  /** Payload `GET /supplier-routes` (amplop `{routes}` atau array). */
  routes: unknown;
  title?: string;
  /** Berapa kiriman yang ditampilkan penuh; sisanya dihitung, bukan dihapus. */
  maks?: number;
  /** Keterangan kecil di bawah kartu (mis. sifat penyaringan data). */
  note?: string;
  /** Saring dulu (mis. hanya kiriman menuju satu lokasi) sebelum memilih. */
  hanya?: (row: SupplierRoute) => boolean;
  /** Pesan pengganti saat tidak ada kiriman; tanpanya kartu tidak dirender. */
  empty?: string;
  /** Tindakan per kiriman (mis. tombol "Periksa kiriman"). */
  action?: (row: SupplierRoute) => ReactNode;
}) {
  const { rows, hidden } = pickShipments(supplierRoutes(routes), maks, hanya);
  if (!rows.length && empty === undefined) return null;

  return (
    <section className="card shipment-card" aria-label={title}>
      <div className="card-header">
        <h2>{title}</h2>
        {rows.length > 0 && (
          <span className="shipment-count">
            {rows.length} kiriman
            {hidden > 0 ? ` · +${hidden} lain` : ""}
          </span>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="evidence-note">{empty}</p>
      ) : (
        <ul className="shipment-list">
          {rows.map((row) => {
          const head = shipmentHeadline(row);
          const safety = shipmentSafetyChip(row);
          const facts = shipmentKeyFacts(row);
          const steps = shipmentSteps(row);
          const details = shipmentDetails(row);
          const events = shipmentEvents(row);
          const routeAudit = shipmentRouteAudit(row);
          return (
            <li key={shipmentKey(row)} className={`shipment-item shipment-item-${head.tone}`}>
              <div className="shipment-top">
                <p className="shipment-title">{shipmentTitle(row)}</p>
                <span className={`shipment-pill shipment-pill-${head.tone}`}>{head.label}</span>
              </div>

              {safety && <span className="shipment-chip shipment-chip-fail">{safety.label}</span>}

              <div className="shipment-mid">
                <ol className="shipment-steps">
                  {steps.map((step) => (
                    <li
                      key={step.key}
                      className={`shipment-step shipment-step-${step.state}`}
                      aria-current={step.state === "active" ? "step" : undefined}
                    >
                      <span className="shipment-step-dot" aria-hidden="true" />
                      <span className="shipment-step-label">{step.label}</span>
                      {step.note && <span className="shipment-step-note">{step.note}</span>}
                    </li>
                  ))}
                </ol>

                <p className="shipment-verdict">{shipmentVerdict(row)}</p>
              </div>

              {facts.length > 0 && (
                <p className="shipment-facts">
                  {facts.map((fact) => (
                    <span key={fact} className="shipment-fact">
                      {fact}
                    </span>
                  ))}
                </p>
              )}

              {action && <div className="shipment-action">{action(row)}</div>}

              <details className="shipment-details">
                <summary>Rincian kiriman</summary>
                <dl className="shipment-detail-list">
                  {details.map((detail) => (
                    <div key={detail.label} className="shipment-detail-row">
                      <dt>{detail.label}</dt>
                      <dd>{detail.value}</dd>
                    </div>
                  ))}
                </dl>

                {/* Riwayat kejadian (kesenjangan #12 riset): hanya kejadian yang
                    PUNYA WAKTU di server, terbaru dulu, dan perkiraan ditandai
                    supaya tidak terbaca sebagai kejadian yang sudah terjadi.
                    Waktu hitung jalur adalah log sistem, bukan kejadian di
                    lapangan — ia jadi catatan kaki audit, bukan baris riwayat. */}
                {(events.length > 0 || routeAudit) && (
                  <div className="shipment-timeline">
                    {events.length > 0 && (
                      <p className="shipment-timeline-head">
                        Riwayat kiriman · {shipmentTimelineLabel(events)}
                      </p>
                    )}
                    {events.length > 0 && (
                      <ol className="shipment-timeline-list">
                        {events.map((event) => (
                          <li
                            key={event.key}
                            className={`shipment-event shipment-event-${event.kind}`}
                          >
                            <span className="shipment-event-line">
                              <span className="shipment-event-title">
                                {event.title}
                                {event.kind === "rencana" && (
                                  <span className="shipment-event-tag">perkiraan</span>
                                )}
                              </span>
                              <span className="shipment-event-at">{event.atLabel}</span>
                            </span>
                            {event.detail && (
                              <span className="shipment-event-detail">{event.detail}</span>
                            )}
                          </li>
                        ))}
                      </ol>
                    )}
                    {routeAudit && <p className="shipment-timeline-note">{routeAudit}</p>}
                  </div>
                )}
              </details>
            </li>
          );
          })}
        </ul>
      )}

      {note && <p className="evidence-note">{note}</p>}
    </section>
  );
}
