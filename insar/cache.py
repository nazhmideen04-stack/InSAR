"""Yerel önbellek: biten analizleri ve bekleyen HyP3 işlerini saklar.

Klasör yapısı:
    outputs/{alan_kodu}_{tarih1}_{tarih2}/
        meta.json
        *_los_disp.tif, *_vert_disp.tif, *_unw_phase.tif, *_corr.tif ...
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .config import CACHE_DIR, JOBS_FILE

# HyP3 INSAR_GAMMA ürününde aradığımız katmanlar (dosya adı sonekleri)
LAYER_SUFFIXES = {
    "los_disp": "Görüş hattı (LOS) yer değiştirme",
    "vert_disp": "Düşey yer değiştirme",
    "unw_phase": "Açılmış faz",
    "corr": "Koherens",
}


def scene_date(scene_name: str) -> str:
    """S1A_IW_SLC__1SDV_20230206T034432_... -> 20230206"""
    return scene_name.split("_")[5][:8]


def area_code(scene1: str, scene2: str) -> str:
    """Aynı sahne çifti her zaman aynı kodu üretir."""
    return hashlib.sha1(f"{scene1}|{scene2}".encode()).hexdigest()[:8]


def result_key(scene1: str, scene2: str) -> str:
    return f"{area_code(scene1, scene2)}_{scene_date(scene1)}_{scene_date(scene2)}"


@dataclass
class CachedResult:
    key: str
    folder: Path
    scene1: str
    scene2: str
    layers: dict[str, str] = field(default_factory=dict)  # sonek -> dosya yolu
    title: str = ""

    @property
    def label(self) -> str:
        d1, d2 = scene_date(self.scene1), scene_date(self.scene2)
        base = f"{d1[6:]}.{d1[4:6]}.{d1[:4]} → {d2[6:]}.{d2[4:6]}.{d2[:4]}"
        return f"{base}  [{self.title}]" if self.title else base


def find_layers(folder: Path) -> dict[str, str]:
    layers = {}
    for tif in folder.rglob("*.tif"):
        for suffix in LAYER_SUFFIXES:
            if tif.stem.endswith("_" + suffix):
                layers[suffix] = str(tif)
    return layers


def lookup(scene1: str, scene2: str) -> CachedResult | None:
    """Önbellekte varsa sonucu döndürür (HyP3'ü hiç beklemeden)."""
    folder = CACHE_DIR / result_key(scene1, scene2)
    meta = folder / "meta.json"
    if not meta.exists():
        return None
    layers = find_layers(folder)
    if "los_disp" not in layers and "unw_phase" not in layers:
        return None
    data = json.loads(meta.read_text(encoding="utf-8"))
    return CachedResult(key=folder.name, folder=folder, scene1=scene1, scene2=scene2,
                        layers=layers, title=data.get("title", ""))


def register(scene1: str, scene2: str, folder: Path, title: str = "") -> CachedResult:
    meta = {"scene1": scene1, "scene2": scene2, "title": title}
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    return lookup(scene1, scene2)


def list_all() -> list[CachedResult]:
    results = []
    for meta in sorted(CACHE_DIR.glob("*/meta.json")):
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
            r = lookup(d["scene1"], d["scene2"])
            if r:
                results.append(r)
        except (KeyError, json.JSONDecodeError):
            continue
    return results


# ---- Bekleyen HyP3 işleri (uygulama kapansa bile kaldığı yerden devam) ----

@dataclass
class PendingJob:
    job_id: str
    scene1: str
    scene2: str
    title: str = ""


def load_pending() -> list[PendingJob]:
    if not JOBS_FILE.exists():
        return []
    try:
        return [PendingJob(**j) for j in json.loads(JOBS_FILE.read_text(encoding="utf-8"))]
    except (json.JSONDecodeError, TypeError):
        return []


def _save_pending(jobs: list[PendingJob]) -> None:
    JOBS_FILE.write_text(json.dumps([asdict(j) for j in jobs], ensure_ascii=False, indent=2),
                         encoding="utf-8")


def add_pending(job: PendingJob) -> None:
    jobs = [j for j in load_pending() if j.job_id != job.job_id]
    jobs.append(job)
    _save_pending(jobs)


def remove_pending(job_id: str) -> None:
    _save_pending([j for j in load_pending() if j.job_id != job_id])
