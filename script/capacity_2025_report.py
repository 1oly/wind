from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

DATASET_URL = "https://api.energidataservice.dk/dataset/CapacityPerMunicipality"
REQUEST_TIMEOUT = 30
DATETIME_FIELDS = [
    "Date",
    "Datetime",
    "DatetimeUTC",
    "Month",
    "HourUTC",
    "HourDK",
]


def fetch_capacity_data(year: int, page_size: int) -> list[dict[str, Any]]:
    offset = 0
    all_records: list[dict[str, Any]] = []
    while True:
        params: dict[str, Any] = {
            "limit": page_size,
            "offset": offset,
            "sort": "Month DESC",
        }
        response = requests.get(
            DATASET_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records", [])
        if not records:
            break
        all_records.extend(records)
        if len(records) < page_size:
            break
        offset += page_size
        if offset >= 50000:
            break
    return all_records


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OSError, ValueError):
            return None
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None
    return None


def _extract_month_key(record: dict[str, Any]) -> tuple[int | None, str | None]:
    rec_year = _to_int(record.get("Year"))
    rec_month = _to_int(record.get("Month"))
    if rec_year and rec_month:
        return rec_year, f"{rec_year:04d}-{rec_month:02d}"

    for field in DATETIME_FIELDS:
        value = record.get(field)
        if not value:
            continue
        dt = _parse_datetime(value)
        if not dt:
            continue
        return dt.year, dt.strftime("%Y-%m")
    return None, None


def aggregate_capacity(records: list[dict[str, Any]], year: int) -> dict[str, dict[str, float]]:
    latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    latest_ts: dict[tuple[str, str], datetime] = {}
    for record in records:
        rec_year, month_key = _extract_month_key(record)
        if rec_year != year or not month_key:
            continue
        muni = (record.get("MunicipalityNo") or "").strip()
        key = (month_key, muni)
        dt = _parse_datetime(record.get("Month"))
        if dt and (latest_ts.get(key) is None or dt > latest_ts[key]):
            latest_ts[key] = dt
            latest_by_key[key] = record

    monthly_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"onshore": 0.0, "offshore": 0.0})
    for (month_key, _), record in latest_by_key.items():
        onshore = record.get("OnshoreWindCapacity")
        offshore = record.get("OffshoreWindCapacity")
        if onshore is not None:
            try:
                monthly_totals[month_key]["onshore"] += float(onshore)
            except (TypeError, ValueError):
                pass
        if offshore is not None:
            try:
                monthly_totals[month_key]["offshore"] += float(offshore)
            except (TypeError, ValueError):
                pass
    return monthly_totals


def save_report(data: dict[str, dict[str, float]], year: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": DATASET_URL,
        "year": year,
        "months": data,
    }
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def print_summary(data: dict[str, dict[str, float]]) -> None:
    header = f"{'Month':<8} {'Onshore (MW)':>14} {'Offshore (MW)':>15} {'Total (MW)':>12}"
    print(header)
    print("-" * len(header))
    for month in sorted(data):
        onshore = data[month].get("onshore", 0.0)
        offshore = data[month].get("offshore", 0.0)
        total = onshore + offshore
        print(f"{month:<8} {onshore:>14.1f} {offshore:>15.1f} {total:>12.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize Onshore/Offshore wind capacity per month using CapacityPerMunicipality dataset."
    )
    parser.add_argument("--year", type=int, default=2025, help="Year to analyze (default: 2025).")
    parser.add_argument(
        "--page-size",
        type=int,
        default=5000,
        help="How many rows to fetch per page from Energi Data Service (default: 5000).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("capacity_per_month_2025.json"),
        help="Optional path to write the JSON summary.",
    )
    parser.add_argument(
        "--sort-order",
        type=str,
        default="DESC",
        choices=["ASC", "DESC"],
        help="Sort order for months (default: DESC).",
    )
    args = parser.parse_args()

    records = fetch_capacity_data(args.year, args.page_size)
    monthly_data = aggregate_capacity(records, args.year)
    if not monthly_data:
        print(f"No capacity records were returned for {args.year}.")
    print_summary(monthly_data)
    save_report(monthly_data, args.year, args.output)
    print(f"\nSaved monthly capacity summary to {args.output}")


if __name__ == "__main__":
    main()
