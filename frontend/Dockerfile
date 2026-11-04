# Image frontend MealChain Guardian (audit DEP-01, 2026-10-24).
#
# Dua target sejak awal, supaya yang dikirim ke server bukan dev server:
#   dev     → `next dev` + bind mount; dipakai `docker compose up` sehari-hari
#             (hot reload, WATCHPACK_POLLING untuk drive exFAT).
#   runner  → hasil `next build` + `next start`; dipakai `docker-compose.prod.yml`.
# Sebelumnya CMD image ini `npm run dev`, jadi image "produksi" menyajikan dev
# server: kompilasi per request, tanpa optimasi build, dan warning dev di console.
#
# `npm run build` memakai scripts/exfat-readlink-patch.cjs; di filesystem Linux
# (dalam image) patch itu tidak berefek apa pun, jadi aman dipakai apa adanya.

FROM node:20-alpine AS deps
WORKDIR /app
# package-lock.json dipakai supaya versi sama dengan dev (npm ci, bukan install).
COPY package.json package-lock.json ./
RUN npm ci

# ---------- target dev ----------
FROM deps AS dev
WORKDIR /app
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---------- target builder ----------
FROM deps AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* di-inline ke bundel KLIEN saat build; menyetelnya di runtime
# kontainer tidak berefek. Deploy VPS (infra/vps/docker-compose.vps.yml)
# meneruskan nilainya lewat `build.args`. Default kosong/false = perilaku lama
# (UI memakai path relatif + proxy Next), jadi build lain tidak berubah.
ARG NEXT_PUBLIC_API_URL=""
ARG NEXT_PUBLIC_USE_MOCK="false"
ARG NEXT_PUBLIC_BASE_PATH=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_USE_MOCK=${NEXT_PUBLIC_USE_MOCK} \
    NEXT_PUBLIC_BASE_PATH=${NEXT_PUBLIC_BASE_PATH}
COPY . .
RUN npm run build

# ---------- target runner (produksi) ----------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# Hanya dependensi runtime: devDependencies (vitest, eslint, typescript) tidak
# ikut ke image produksi.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./next.config.js
COPY --from=builder /app/next-env.d.ts ./next-env.d.ts

# Jalankan sebagai user non-root (node:20-alpine sudah menyediakan uid 1000).
RUN chown -R node:node /app
USER node

EXPOSE 3000
# `next start` = server produksi hasil build, bukan dev server.
# Catatan: dijalankan lewat `npm run start`. Mengganti ke `node node_modules/next/
# dist/bin/next start` (PID 1 = server, SIGTERM lebih rapi) belum diverifikasi
# karena rebuild image di mesin ini berulang kali menghabiskan resource Docker
# Desktop — jangan diubah tanpa build + uji ulang.
CMD ["npm", "run", "start"]
