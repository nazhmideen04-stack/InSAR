"""ASF HyP3 bulut işleme: iş gönderme, takip ve indirme."""

from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path
from typing import Callable

import hyp3_sdk as sdk

from . import cache
from .config import CACHE_DIR, POLL_INTERVAL_SEC

Log = Callable[[str], None]


def connect(username: str | None = None, password: str | None = None,
            token: str | None = None) -> sdk.HyP3:
    """HyP3 oturumu açar.

    Öncelik: verilen token > kullanıcı adı/şifre > EARTHDATA_TOKEN ortam değişkeni
    > ~/.netrc (machine urs.earthdata.nasa.gov).
    """
    token = token or os.environ.get("EARTHDATA_TOKEN")
    if token:
        return sdk.HyP3(token=token, prompt=False)
    if username and password:
        return sdk.HyP3(username=username, password=password, prompt=False)
    return sdk.HyP3(prompt=False)


def credits_text(hyp3: sdk.HyP3) -> str:
    try:
        c = hyp3.check_credits()
        return f"Kalan kredi: {c}" if c is not None else "Kredi: sınırsız"
    except Exception as e:  # noqa: BLE001 - bilgi amaçlı
        return f"Kredi bilgisi alınamadı ({e})"


def submit(hyp3: sdk.HyP3, scene1: str, scene2: str, title: str = "",
           looks: str = "20x4") -> sdk.Job:
    """Faz açmalı (SNAPHU) D-InSAR işini HyP3'e gönderir."""
    batch = hyp3.submit_insar_job(
        granule1=scene1,
        granule2=scene2,
        name=(title or "insar_masaustu")[:100],
        looks=looks,                     # 20x4 ~80 m (hızlı) / 10x2 ~40 m (detaylı)
        include_dem=True,
        include_inc_map=False,
        include_look_vectors=False,
        include_displacement_maps=True,  # *_los_disp.tif ve *_vert_disp.tif (metre)
        apply_water_mask=True,
    )
    job = batch.jobs[0]
    cache.add_pending(cache.PendingJob(job.job_id, scene1, scene2, title))
    return job


def wait(hyp3: sdk.HyP3, job: sdk.Job, log: Log,
         should_stop: Callable[[], bool] = lambda: False,
         interval: int = POLL_INTERVAL_SEC) -> sdk.Job:
    """İş bitene kadar periyodik sorgular (hyp3.watch yerine; arayüz kilitlenmez)."""
    start = time.time()
    last = None
    while True:
        job = hyp3.refresh(job)
        if job.status_code != last:
            log(f"İş durumu: {job.status_code}")
            last = job.status_code
        if job.complete():
            return job
        if should_stop():
            raise InterruptedError("Kullanıcı tarafından durduruldu (iş bulutta devam ediyor).")
        dk = int((time.time() - start) / 60)
        log(f"Bekleniyor… {dk} dk geçti")
        for _ in range(interval):
            if should_stop():
                raise InterruptedError("Kullanıcı tarafından durduruldu (iş bulutta devam ediyor).")
            time.sleep(1)


def download(job: sdk.Job, scene1: str, scene2: str, title: str, log: Log) -> cache.CachedResult:
    if not job.succeeded():
        raise RuntimeError(f"HyP3 işi başarısız oldu (durum: {job.status_code}).")
    folder = CACHE_DIR / cache.result_key(scene1, scene2)
    folder.mkdir(parents=True, exist_ok=True)
    log("Sonuç indiriliyor…")
    for f in job.download_files(folder):
        f = Path(f)
        if f.suffix == ".zip":
            log("Arşiv açılıyor…")
            with zipfile.ZipFile(f) as z:
                # Sadece GeoTIFF ve metadata; zip dışına yazmaya çalışan yolları reddet
                for member in z.namelist():
                    target = (folder / member).resolve()
                    if folder.resolve() not in target.parents:
                        continue
                    if member.endswith((".tif", ".txt", ".xml", ".json")):
                        z.extract(member, folder)
            f.unlink()
    result = cache.register(scene1, scene2, folder, title)
    if result is None:
        raise RuntimeError("İndirilen ürün içinde deformasyon katmanı bulunamadı.")
    cache.remove_pending(job.job_id)
    return result


def run_pair(hyp3: sdk.HyP3, scene1: str, scene2: str, title: str, log: Log,
             should_stop: Callable[[], bool] = lambda: False,
             looks: str = "20x4") -> cache.CachedResult:
    """Önce önbelleğe bakar; yoksa (ya da bekleyen iş varsa) HyP3 üzerinden üretir."""
    hit = cache.lookup(scene1, scene2)
    if hit:
        log("Önbellekte bulundu, anında yükleniyor.")
        return hit

    pending = next((p for p in cache.load_pending()
                    if p.scene1 == scene1 and p.scene2 == scene2), None)
    if pending:
        log(f"Daha önce gönderilmiş iş bulundu ({pending.job_id[:8]}…), takip ediliyor.")
        job = hyp3.get_job_by_id(pending.job_id)
        if job.failed() or job.expired():
            cache.remove_pending(pending.job_id)
            job = None
    else:
        job = None

    if job is None:
        log("HyP3'e yeni iş gönderiliyor…")
        job = submit(hyp3, scene1, scene2, title, looks)
        log(f"İş gönderildi: {job.job_id}. Genelde 15-40 dk sürer.")

    job = wait(hyp3, job, log, should_stop)
    return download(job, scene1, scene2, title, log)
