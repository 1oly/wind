# Source:
# https://github.com/electricitymaps/electricitymaps-contrib/blob/b5b70117ef891c7e42d2cdf712ad07378027d999/electricitymap/contrib/parsers/DK.py
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

DATASET_URL = "https://api.energidataservice.dk/dataset/ElectricityProdex5MinRealtime"
PRICE_AREAS = ("DK1", "DK2")
DEFAULT_OUTPUT = Path(__file__).with_name("wind_actuals.json")
REQUEST_TIMEOUT = 30


@dataclass
class PriceAreaProduction:
    price_area: str
    timestamp_utc: str
    onshore_mw: float | None
    offshore_mw: float | None

    @property
    def total_mw(self) -> float | None:
        values = [
            value for value in (self.onshore_mw, self.offshore_mw) if _is_valid_number(value)
        ]
        if not values:
            return None
        return sum(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "price_area": self.price_area,
            "timestamp_utc": self.timestamp_utc,
            "onshore_mw": self.onshore_mw,
            "offshore_mw": self.offshore_mw,
            "total_mw": self.total_mw,
        }


def _is_valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _coerce_float(value: Any) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted):
        return None
    return converted


def fetch_latest_production(
    price_area: str,
    session: requests.Session,
    limit: int,
) -> PriceAreaProduction:
    params = {
        "limit": limit,
        "filter": json.dumps({"PriceArea": price_area}),
    }
    response = session.get(DATASET_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("records") or []
    if not records:
        raise RuntimeError(f"No production records returned for {price_area}.")

    latest_record = max(records, key=lambda record: record.get("Minutes5UTC", ""))
    timestamp = latest_record.get("Minutes5UTC")
    if not timestamp:
        raise RuntimeError(f"No timestamp found for latest {price_area} record.")

    return PriceAreaProduction(
        price_area=price_area,
        timestamp_utc=timestamp,
        onshore_mw=_coerce_float(latest_record.get("OnshoreWindPower")),
        offshore_mw=_coerce_float(latest_record.get("OffshoreWindPower")),
    )


def summarize_totals(entries: list[PriceAreaProduction]) -> dict[str, Any]:
    totals = {
        "onshore_mw": _sum_numbers(entry.onshore_mw for entry in entries),
        "offshore_mw": _sum_numbers(entry.offshore_mw for entry in entries),
    }
    totals["total_mw"] = _sum_numbers(totals.values())
    return totals


def _sum_numbers(values: Any) -> float | None:
    total = 0.0
    seen_value = False
    for value in values:
        if _is_valid_number(value):
            total += float(value)
            seen_value = True
    return total if seen_value else None


def collect_production(limit: int) -> dict[str, Any]:
    session = requests.Session()
    entries: list[PriceAreaProduction] = []
    for price_area in PRICE_AREAS:
        entries.append(fetch_latest_production(price_area, session, limit))

    areas = {entry.price_area: entry.to_dict() for entry in entries}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": DATASET_URL,
        "areas": areas,
        "totals": summarize_totals(entries),
        "latest_timestamp_utc": compute_latest_timestamp(entries),
    }
    return payload


def compute_latest_timestamp(entries: list[PriceAreaProduction]) -> str | None:
    timestamps = [
        entry.timestamp_utc for entry in entries if isinstance(entry.timestamp_utc, str)
    ]
    if not timestamps:
        return None
    return max(timestamps)


def write_output(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch DK1/DK2 onshore and offshore wind production from Energi Data Service."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to store the production JSON file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of rows to request per price area (defaults to 500).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = collect_production(limit=max(1, args.limit))
    write_output(data, args.output)
    print(f"Wrote wind production data to {args.output}")


if __name__ == "__main__":
    main()
