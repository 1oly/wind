#!/usr/bin/env python3
"""Generate representative wind turbine power curves using PyWake."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List

import numpy as np

try:
    from py_wake.wind_turbines import WindTurbine
    from py_wake.wind_turbines.power_ct_functions import CubePowerSimpleCt
except ImportError as exc:  # pragma: no cover - dependency provided by user
    raise SystemExit(
        "PyWake is required to run this script. Install it with 'pip install py_wake' before executing."
    ) from exc

WT_DATA_PATH = Path(__file__).resolve().parents[1] / "wt_2025jan.json"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "power_curves"
OUTPUT_PATH = OUTPUT_DIR / "power_curves.json"
WS_VALUES = np.arange(0.0, 30.5, 0.5)
DEFAULT_WS_CUTIN = 3.0
DEFAULT_WS_RATED = 12.0
DEFAULT_WS_CUTOUT = 25.0
CLUSTER_COUNT = 50  # Set to None to export one curve per turbine


@dataclass(frozen=True)
class TurbineDefinition:
    id: str
    name: str
    capacity_kw: float
    rotor_diam_m: float
    hub_height_m: float
    ws_cutin: float = DEFAULT_WS_CUTIN
    ws_rated: float = DEFAULT_WS_RATED
    ws_cutout: float = DEFAULT_WS_CUTOUT
    ct: float = 8 / 9
    ct_idle: float = 0.03


def load_turbine_properties(path: Path) -> Iterable[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Cannot find turbine dataset: {path}")
    with path.open() as f:
        data = json.load(f)
    for feature in data.get('features', []):
        props = feature.get('properties') or {}
        if props.get('capacity_kW') is None:
            continue
        yield props


def _kmeans_1d(values: np.ndarray, cluster_count: int, iterations: int = 25) -> np.ndarray:
    """Very small 1-D k-means helper to avoid heavyweight dependencies."""
    if cluster_count >= len(values):
        return values.copy()
    centroids = np.linspace(values.min(), values.max(), cluster_count)
    for _ in range(iterations):
        distances = np.abs(values[None, :] - centroids[:, None])
        labels = np.argmin(distances, axis=0)
        new_centroids = np.array([
            values[labels == i].mean() if np.any(labels == i) else centroids[i]
            for i in range(cluster_count)
        ])
        if np.allclose(new_centroids, centroids):
            break
        centroids = new_centroids
    return centroids


def bucket_turbines(properties: Iterable[Dict]) -> List[TurbineDefinition]:
    entries = [p for p in properties if p.get('capacity_kW') is not None]
    if not entries:
        return []

    capacities = np.array([p.get('capacity_kW') or 0.0 for p in entries], dtype=float)
    order = np.argsort(capacities)
    capacities = capacities[order]
    entries = [entries[i] for i in order]

    cluster_target = len(entries) if CLUSTER_COUNT is None else max(1, int(CLUSTER_COUNT))
    cluster_target = min(cluster_target, len(entries))

    centroids = _kmeans_1d(capacities, cluster_target)
    distances = np.abs(capacities[None, :] - centroids[:, None])
    labels = np.argmin(distances, axis=0)

    definitions: List[TurbineDefinition] = []
    for idx in range(cluster_target):
        cluster_items = [entries[i] for i in range(len(entries)) if labels[i] == idx]
        if not cluster_items:
            continue
        capacity_kw_avg = mean(e.get('capacity_kW') or 0 for e in cluster_items)
        rotor_avg = mean(e.get('rotor_diam_m') or 0 for e in cluster_items)
        hub_avg = mean(e.get('hub_height_m') or 0 for e in cluster_items)
        max_bucket = int((max(e.get('capacity_kW') or 0 for e in cluster_items)) // 1000)
        min_bucket = int((min(e.get('capacity_kW') or 0 for e in cluster_items)) // 1000)
        ws_rated = DEFAULT_WS_RATED + min(max_bucket, 5) * 0.2
        label = f"{min_bucket}-{max_bucket} MW cluster" if min_bucket != max_bucket else f"~{max_bucket} MW cluster"
        definitions.append(TurbineDefinition(
            id=f"cluster_{idx:02d}",
            name=label,
            capacity_kw=capacity_kw_avg,
            rotor_diam_m=rotor_avg,
            hub_height_m=hub_avg,
            ws_rated=ws_rated,
        ))

    definitions.sort(key=lambda d: d.capacity_kw)
    return definitions


def build_curve(defn: TurbineDefinition) -> dict:
    power_function = CubePowerSimpleCt(
        ws_cutin=defn.ws_cutin,
        ws_cutout=defn.ws_cutout,
        ws_rated=defn.ws_rated,
        power_rated=defn.capacity_kw,
        power_unit='kW',
        ct=defn.ct,
        ct_idle=defn.ct_idle,
        additional_models=[],  # only need the analytical curve
    )
    wt = WindTurbine(
        name=defn.name,
        diameter=defn.rotor_diam_m,
        hub_height=defn.hub_height_m,
        powerCtFunction=power_function,
    )
    power_mw = (wt.power(WS_VALUES) / 1e6).tolist()
    result = asdict(defn)
    result.update({
        "capacity_mw": defn.capacity_kw / 1000.0,
        "ws": WS_VALUES.tolist(),
        "power_mw": power_mw,
    })
    return result


def main() -> None:
    properties = list(load_turbine_properties(WT_DATA_PATH))
    definitions = bucket_turbines(properties)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = [build_curve(defn) for defn in definitions]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ws_interval": WS_VALUES[1] - WS_VALUES[0],
        "source": WT_DATA_PATH.name,
        "turbines": curves,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {len(curves)} power curves to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
