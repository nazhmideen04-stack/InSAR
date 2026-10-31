"""Uygulama genelindeki ayarlar ve klasör yolları."""

from pathlib import Path
import os

APP_NAME = "InSAR Masaüstü"

# Tüm çıktılar kullanıcının ev dizininde saklanır (önbellek dahil).
DATA_DIR = Path(os.environ.get("INSAR_DATA_DIR", Path.home() / "InSAR_Masaustu"))
CACHE_DIR = DATA_DIR / "outputs"
JOBS_FILE = DATA_DIR / "bekleyen_isler.json"

# Sahne arama: seçilen tarihin etrafında kaç gün tolerans tanınsın
# (Sentinel-1 aynı yörüngeyi 12 günde bir tekrar geçer).
DATE_TOLERANCE_DAYS = 6

# Uzun zaman aralıklarında koherens kaybı artar; bu sınırın üstünde uyarı ver.
MAX_RECOMMENDED_SPAN_DAYS = 48

# HyP3 iş durumu sorgulama aralığı (saniye)
POLL_INTERVAL_SEC = 30

for d in (DATA_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)
