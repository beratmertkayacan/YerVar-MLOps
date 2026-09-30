#!/usr/bin/env bash
# MLflow arayüzünü açar: eğitim koşularını tarayıcıda görmek ve karşılaştırmak için.
#
# Çalıştırma (proje içinde herhangi bir yerden):  bash kesif/mlflow_arayuz.sh
# Kapatmak için bu terminalde Ctrl+C.
#
# Kayıt dosyasının yolunu tam (mutlak) veriyoruz. Göreli yol verilirse ve komut
# başka bir klasörden çalıştırılırsa MLflow orada yeni, boş bir kayıt açar ve
# arayüzde hiçbir koşu görünmez.

set -euo pipefail
cd "$(dirname "$0")/.."

DB="$(pwd)/veri/mlflow.db"
PORT="${PORT:-5001}"   # 5000'i macOS AirPlay kullanıyor

if [ ! -f "$DB" ]; then
  echo "Kayıt yok: $DB"
  echo "Önce bir eğitim çalıştır:  DEPO_TURU=blob python -m yervar.egitim.egit"
  exit 1
fi

command -v mlflow >/dev/null || {
  echo "mlflow bulunamadı. Sanal ortam açık mı?  source .venv/bin/activate"; exit 1;
}

export MLFLOW_DISABLE_AGENT_HINT=1
echo "Arayüz: http://127.0.0.1:$PORT  (birkaç saniye içinde tarayıcıda açılacak)"
( sleep 5 && open "http://127.0.0.1:$PORT" ) &
exec mlflow ui --backend-store-uri "sqlite:///$DB" --port "$PORT"
