# =============================================================================
# backend.Dockerfile — image backend untuk VPS (konteks build = AKAR repo)
# =============================================================================
#
# Kenapa terpisah dari backend/Dockerfile: review 9 agen mengimpor paket
# `agent/` yang berada di AKAR repo, di luar `backend/`. Image yang dibangun
# hanya dari konteks `backend/` tidak memuat paket itu, sehingga di VPS
# review gagal dengan:
#     ModuleNotFoundError: No module named 'agent'
# dan papan "Kualitas per agen" kosong tanpa penjelasan.
#
# Build (dari akar repo):
#   docker build -f infra/vps/backend.Dockerfile -t mealchain-vps-backend .
#
# PYTHONPATH memuat /app (kode backend) dan /opt (induk paket agent/), jadi
# `import app...` dan `import agent...` sama-sama bekerja tanpa saling menimpa.
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Kode backend: isi backend/ menjadi /app (sama seperti backend/Dockerfile).
COPY backend/ /app/

# Paket agen: agent/ menjadi /opt/agent supaya bisa diimpor sebagai `agent`.
COPY agent/ /opt/agent/

ENV PYTHONPATH=/app:/opt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
