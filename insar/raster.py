"""GeoTIFF -> harita bindirmesi (PNG) ve noktadan değer okuma."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform
from matplotlib import colormaps
from matplotlib.colors import TwoSlopeNorm, Normalize
from PIL import Image

# Katman türüne göre birim dönüşümü ve renk skalası
LAYER_STYLE = {
    "los_disp": {"scale": 1000.0, "unit": "mm", "cmap": "RdBu_r", "diverging": True},
    "vert_disp": {"scale": 1000.0, "unit": "mm", "cmap": "RdBu_r", "diverging": True},
    "unw_phase": {"scale": 1.0, "unit": "rad", "cmap": "twilight_shifted", "diverging": True},
    "corr": {"scale": 1.0, "unit": "", "cmap": "gray", "diverging": False},
}

MAX_PIXELS = 2048  # Haritaya gönderilen PNG'nin en uzun kenarı


@dataclass
class Overlay:
    png_path: str
    bounds: tuple[float, float, float, float]  # güney, batı, kuzey, doğu (Leaflet sırası)
    vmin: float
    vmax: float
    unit: str
    cmap: str
    stats: dict


def _read_wgs84(path: str, scale: float):
    with rasterio.open(path) as src:
        dst_crs = "EPSG:4326"
        tr, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height,
                                               *src.bounds)
        # Çok büyük rasterleri küçült (harita gösterimi için yeterli)
        f = max(w, h) / MAX_PIXELS
        if f > 1:
            w, h = int(w / f), int(h / f)
            tr = tr * tr.scale(f, f)
        data = np.full((h, w), np.nan, dtype="float32")
        src_arr = src.read(1).astype("float32")
        if src.nodata is not None:
            src_arr[src_arr == src.nodata] = np.nan
        src_arr[src_arr == 0] = np.nan  # HyP3 ürünlerinde 0 = veri yok / su maskesi
        reproject(src_arr, data, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=tr, dst_crs=dst_crs, resampling=Resampling.bilinear,
                  src_nodata=np.nan, dst_nodata=np.nan)
    west, north = tr.c, tr.f
    east, south = west + tr.a * w, north + tr.e * h
    return data * scale, (south, west, north, east)


def auto_limit(tif_path: str, layer: str) -> float:
    """Simetrik renk skalası için %98'lik mutlak değer."""
    style = LAYER_STYLE.get(layer, LAYER_STYLE["los_disp"])
    data, _ = _read_wgs84(tif_path, style["scale"])
    valid = data[np.isfinite(data)]
    return float(np.percentile(np.abs(valid), 98)) if valid.size else 1.0


def make_overlay(tif_path: str, layer: str, out_dir: Path,
                 limit: float | None = None) -> Overlay:
    """limit verilirse renk skalası [-limit, +limit] olur (karşılaştırmada ortak skala)."""
    style = LAYER_STYLE.get(layer, LAYER_STYLE["los_disp"])
    data, bounds = _read_wgs84(tif_path, style["scale"])
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        raise ValueError("Rasterde geçerli piksel yok.")

    if style["diverging"]:
        lim = limit or float(np.nanpercentile(np.abs(valid), 98)) or 1.0
        vmin, vmax = -lim, lim
        norm = TwoSlopeNorm(vcenter=0.0, vmin=vmin, vmax=vmax)
    else:
        vmin, vmax = 0.0, 1.0
        norm = Normalize(vmin, vmax)

    rgba = (colormaps[style["cmap"]](norm(np.nan_to_num(data))) * 255).astype("uint8")
    rgba[..., 3] = np.where(np.isfinite(data), 255, 0)

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{Path(tif_path).stem}_onizleme.png"
    Image.fromarray(rgba, "RGBA").save(png, optimize=True)

    stats = {
        "min": float(valid.min()),
        "max": float(valid.max()),
        "ortalama": float(valid.mean()),
        "std": float(valid.std()),
    }
    return Overlay(str(png), bounds, vmin, vmax, style["unit"], style["cmap"], stats)


def colorbar_css(cmap: str, steps: int = 11) -> str:
    """Lejant için CSS linear-gradient üretir."""
    cm = colormaps[cmap]
    stops = []
    for i in range(steps):
        r, g, b, _ = cm(i / (steps - 1))
        stops.append(f"rgb({int(r*255)},{int(g*255)},{int(b*255)}) {i*100/(steps-1):.0f}%")
    return "linear-gradient(to right, " + ", ".join(stops) + ")"


def sample(tif_path: str, lat: float, lon: float, layer: str) -> float | None:
    """Verilen enlem/boylamdaki piksel değerini (dönüştürülmüş birimle) okur."""
    style = LAYER_STYLE.get(layer, LAYER_STYLE["los_disp"])
    with rasterio.open(tif_path) as src:
        xs, ys = transform("EPSG:4326", src.crs, [lon], [lat])
        row, col = src.index(xs[0], ys[0])
        if not (0 <= row < src.height and 0 <= col < src.width):
            return None
        v = src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
        if (src.nodata is not None and v == src.nodata) or v == 0 or not np.isfinite(v):
            return None
        return float(v) * style["scale"]
