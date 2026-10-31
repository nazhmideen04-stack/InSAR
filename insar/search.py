"""ASF'de Sentinel-1 SLC sahnesi arama ve InSAR çifti eşleştirme."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import asf_search as asf

from .config import DATE_TOLERANCE_DAYS


@dataclass
class Scene:
    name: str
    time: datetime
    path: int
    frame: int
    direction: str
    polarization: str

    @property
    def label(self) -> str:
        return f"{self.time:%Y-%m-%d} | yol {self.path} / çerçeve {self.frame} | {self.direction}"


@dataclass
class InsarPair:
    reference: Scene   # eski tarih
    secondary: Scene   # yeni tarih

    @property
    def span_days(self) -> int:
        return abs((self.secondary.time.date() - self.reference.time.date()).days)

    @property
    def label(self) -> str:
        r, s = self.reference, self.secondary
        yon = "Yükselen" if r.direction.upper().startswith("ASC") else "Alçalan"
        return (f"{r.time:%d.%m.%Y} → {s.time:%d.%m.%Y}  ({self.span_days} gün)  "
                f"| Yol {r.path}, Çerçeve {r.frame}, {yon}")


def bbox_to_wkt(west: float, south: float, east: float, north: float) -> str:
    return (f"POLYGON(({west} {south},{east} {south},{east} {north},"
            f"{west} {north},{west} {south}))")


def _to_scene(product) -> Scene | None:
    p = product.properties
    try:
        t = datetime.fromisoformat(p["startTime"].replace("Z", "+00:00"))
        return Scene(
            name=p["sceneName"],
            time=t,
            path=int(p["pathNumber"]),
            frame=int(p["frameNumber"]),
            direction=str(p.get("flightDirection") or ""),
            polarization=str(p.get("polarization") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _search_around(wkt: str, day: date, tol: int) -> list[Scene]:
    start = datetime.combine(day - timedelta(days=tol), datetime.min.time())
    end = datetime.combine(day + timedelta(days=tol), datetime.max.time())
    results = asf.geo_search(
        platform=asf.PLATFORM.SENTINEL1,
        processingLevel=asf.PRODUCT_TYPE.SLC,
        beamMode=asf.BEAMMODE.IW,
        intersectsWith=wkt,
        start=start,
        end=end,
    )
    scenes = [s for s in (_to_scene(r) for r in results) if s]
    # HyP3 InSAR için VV polarizasyon gerekli
    return [s for s in scenes if "VV" in s.polarization.upper()]


def find_pairs(wkt: str, date1: date, date2: date,
               tol: int = DATE_TOLERANCE_DAYS) -> list[InsarPair]:
    """İki tarihe en yakın, aynı yörünge/çerçeveden gelen sahne çiftlerini döndürür.

    Sonuçlar, seçilen tarihlere en yakın olandan başlayarak sıralanır.
    """
    if date1 > date2:
        date1, date2 = date2, date1

    first = _search_around(wkt, date1, tol)
    second = _search_around(wkt, date2, tol)

    pairs: list[InsarPair] = []
    seen = set()
    for a in first:
        for b in second:
            if a.name == b.name or b.time <= a.time:
                continue
            # InSAR için aynı yörünge (path) ve aynı çerçeve şart
            if a.path != b.path or a.frame != b.frame:
                continue
            key = (a.name, b.name)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(InsarPair(a, b))

    def score(p: InsarPair) -> int:
        return (abs((p.reference.time.date() - date1).days)
                + abs((p.secondary.time.date() - date2).days))

    pairs.sort(key=score)
    return pairs
