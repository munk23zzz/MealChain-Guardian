<#
  joule-login.ps1 - siapkan .env dari joule-key.json, lalu `joule login --use-env` + `joule status`
  untuk jembatan MealChain Guardian -> SAP Joule (lihat sap-joule/docs/runbook-cf-joule.md §7).

  Pemakaian (dari folder mana pun):
    powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1
    powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1 -Force
    powershell -ExecutionPolicy Bypass -File sap-joule\scripts\joule-login.ps1 -DryRun

  Kenapa skrip dan bukan perintah tempel: clientsecret tidak pernah lewat baris perintah
  (riwayat PSReadLine) dan tidak pernah dicetak ke layar. Nilai dibaca dari
  sap-joule\joule-key.json (hasil keybroker, sudah gitignored) lalu ditulis ke
  sap-joule\joule\.env (juga gitignored).

  Email + password IAS TIDAK ada di skrip ini: CLI menanyakannya sendiri secara interaktif,
  jadi kredensial pribadi tetap hanya kamu yang mengetik.
#>
[CmdletBinding()]
param(
  [switch]$Force,              # tulis ulang .env dari joule-key.json walau sudah ada
  [switch]$DryRun,             # hanya siapkan .env, jangan panggil `joule login`
  [string]$ApiUrl = ''         # override JOULE_API_URL (kosong = nilai bawaan tenant tim)
)

$ErrorActionPreference = 'Stop'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path   # ...\sap-joule\scripts
$sapJoule   = Split-Path -Parent $scriptDir                     # ...\sap-joule
$jouleDir   = Join-Path $sapJoule 'joule'
$keyFile    = Join-Path $sapJoule 'joule-key.json'
$envFile    = Join-Path $jouleDir '.env'
$tmplFile   = Join-Path $jouleDir 'joule.env.example'
$apiDefault = 'https://aws-sap-hackathon-si4ykj9d.ap10.sapdas.cloud.sap'

function Fail([string]$msg) { Write-Host "GAGAL: $msg" -ForegroundColor Red; exit 1 }
function Info([string]$msg) { Write-Host $msg -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host $msg -ForegroundColor Green }

Info "== 1/4 Cek prasyarat =="

if (-not (Test-Path $keyFile)) {
  Fail ("tidak ada {0}`n  ambil dulu dari keybroker:`n  curl.exe -s -o `"{0}`" https://hackathon-keybroker.cfapps.ap10.hana.ondemand.com/joule/4sehat3trio-key" -f $keyFile)
}
if (-not (Test-Path $tmplFile)) { Fail "tidak ada templat $tmplFile" }

$k = (Get-Content $keyFile -Raw | ConvertFrom-Json).uaa
if (-not $k.clientid -or -not $k.clientsecret -or -not $k.url) {
  Fail "joule-key.json tidak memuat uaa.clientid + uaa.clientsecret + uaa.url"
}
Ok  "  joule-key.json OK (clientid + clientsecret + url terbaca)"
Write-Host ("  authurl (dari key) = {0}" -f $k.url) -ForegroundColor DarkGray
Write-Host  "  apiurl             = $apiDefault" -ForegroundColor DarkGray

Info "`n== 2/4 Siapkan .env =="

$tulisUlang = $Force.IsPresent
if (-not $tulisUlang -and (Test-Path $envFile)) {
  $isiLama = Get-Content $envFile -Raw
  if ($isiLama -notmatch '(?m)^JOULE_CLIENT_SECRET=.+') { $tulisUlang = $true }
}
if (-not (Test-Path $envFile)) { $tulisUlang = $true }

if ($tulisUlang) {
  $apiFinal = if ($ApiUrl) { $ApiUrl } else { $apiDefault }
  # Baca templat sebagai UTF-8 eksplisit: di PS 5.1, Get-Content tanpa -Encoding membaca
  # berkas tanpa BOM sebagai ANSI sehingga karakter non-ASCII di komentar jadi mojibake.
  $templat = [IO.File]::ReadAllLines($tmplFile, [Text.Encoding]::UTF8)
  # Ganti nilai per baris dengan penggabungan string murni (bukan -replace),
  # supaya karakter `$` di dalam clientsecret tidak ditafsirkan sebagai regex.
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($ln in $templat) {
    switch -Regex ($ln) {
      '^JOULE_CLIENT_ID='     { $out.Add("JOULE_CLIENT_ID=$($k.clientid)") }
      '^JOULE_CLIENT_SECRET=' { $out.Add("JOULE_CLIENT_SECRET=$($k.clientsecret)") }
      '^JOULE_AUTH_URL='      { $out.Add("JOULE_AUTH_URL=$($k.url)") }
      '^JOULE_API_URL='       { $out.Add("JOULE_API_URL=$apiFinal") }
      default                 { $out.Add($ln) }
    }
  }
  $utf8TanpaBom = New-Object System.Text.UTF8Encoding($false)   # PS 5.1 default-nya BOM
  [IO.File]::WriteAllLines($envFile, $out, $utf8TanpaBom)
  Ok "  ditulis: $envFile"
} else {
  Write-Host "  pakai .env yang sudah ada (tidak ditimpa; tambahkan -Force kalau mau menulis ulang)" -ForegroundColor Yellow
}

Write-Host "  isi (rahasia tidak dicetak):"
Get-Content $envFile | Where-Object { $_ -match '^JOULE_' } | ForEach-Object {
  $n, $v = $_ -split '=', 2
  $tampil = if ($v) { "<terisi $($v.Length) char>" } else { '<kosong>' }
  if ($n -match 'SECRET|PASSWORD') { $tampil = if ($v) { "<rahasia $($v.Length) char>" } else { '<kosong>' } }
  "    $n = $tampil"
}

if ($DryRun) { Info "`n-DryRun: berhenti sebelum `joule login`."; exit 0 }

Info "`n== 3/4 Login =="
if (-not (Get-Command joule -ErrorAction SilentlyContinue)) {
  Fail "perintah 'joule' tidak ada di PATH. Pasang: npm i -g @sap/joule-studio-cli (butuh Node 24-26)."
}
Write-Host ("  joule: {0}" -f ((joule --version 2>&1 | Where-Object { $_.Trim() }) -join ' '))
Write-Host  "  Saat diminta: ketik email IAS, lalu password (tersembunyi saat diketik)." -ForegroundColor DarkGray

Push-Location $jouleDir
try {
  joule login --use-env .env
  if ($LASTEXITCODE -ne 0) {
    Write-Host "`nLogin keluar dengan kode $LASTEXITCODE." -ForegroundColor Red
    Write-Host "Kalau errornya soal auth, ulangi dengan authurl cadangan dari README tutorial:" -ForegroundColor Yellow
    Write-Host "  joule login --no-app-tid --authurl 'https://auisywroy.authentication.ap10.hana.ondemand.com' ``" -ForegroundColor Yellow
    Write-Host "    --apiurl '$apiDefault' -c `"`$k.clientid`" -s `"`$k.clientsecret`"" -ForegroundColor Yellow
    Write-Host "  (pakai -c/-s hanya sebagai upaya terakhir: nilainya akan tampil di riwayat shell)" -ForegroundColor Yellow
    exit $LASTEXITCODE
  }

  Info "`n== 4/4 Verifikasi =="
  joule status
  Ok "`nSelesai. Kalau statusnya 'Logged in', lanjut ke runbook §7:"
  Write-Host "  cd $jouleDir" -ForegroundColor DarkGray
  Write-Host "  joule lint" -ForegroundColor DarkGray
  Write-Host '  joule deploy -c -n "<nama-asisten>"' -ForegroundColor DarkGray
  Write-Host "  joule launch <nama-asisten>   # nama digital assistant, bukan nama folder capability" -ForegroundColor DarkGray
}
finally { Pop-Location }
