#!/usr/bin/env python3
"""Generate dedup-evidence.json for raw/2026-10-10 from saved arXiv XML + X/FRED.

Run from repo root or from this directory:
  python3 raw/2026-10-10/dedup-evidence.py
Writes dedup-evidence.json next to this script.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def arxiv_id_from_entry_id(entry_id: str) -> str:
    """http://arxiv.org/abs/2610.12466v1 -> 2610.12466v1"""
    return entry_id.rstrip("/").split("/")[-1]


def load_arxiv_ids_by_file() -> dict[str, list[str]]:
    arxiv_dir = HERE / "arxiv"
    by_file: dict[str, list[str]] = {}
    for xml_path in sorted(arxiv_dir.glob("*.xml")):
        root = ET.parse(xml_path).getroot()
        ids = [
            arxiv_id_from_entry_id(entry.find("a:id", ATOM_NS).text)
            for entry in root.findall("a:entry", ATOM_NS)
        ]
        by_file[xml_path.name] = ids
    return by_file


def load_x_unique_count() -> dict:
    x_dir = HERE / "x"
    all_ids: list[str] = []
    per_file: dict[str, int] = {}
    for path in sorted(x_dir.glob("[0-9]*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = [str(item["id"]) for item in data.get("data", [])]
        per_file[path.name] = len(ids)
        all_ids.extend(ids)
    return {
        "total_entries": len(all_ids),
        "unique_ids": len(set(all_ids)),
        "per_file": per_file,
    }


def load_fred_unique_count() -> dict:
    fred_dir = HERE / "fred"
    per_series: dict[str, int] = {}
    total = 0
    for path in sorted(fred_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        n = len(data.get("observations", []))
        per_series[path.stem] = n
        total += n
    return {
        "series_count": len(per_series),
        "total_observations": total,
        "per_series": per_series,
    }


def build_evidence() -> dict:
    by_file = load_arxiv_ids_by_file()
    id_to_files: dict[str, list[str]] = defaultdict(list)
    for fname, ids in by_file.items():
        for aid in ids:
            id_to_files[aid].append(fname)

    total_entries = sum(len(ids) for ids in by_file.values())
    unique_ids = sorted(id_to_files)
    # "dupes" = redundant entries beyond the unique set (total - unique)
    duplicate_entry_count = total_entries - len(unique_ids)

    multi_file = {
        aid: files
        for aid, files in sorted(id_to_files.items())
        if len(files) > 1
    }

    return {
        "date": "2026-10-10",
        "arxiv": {
            "per_query_file": by_file,
            "ids_in_multiple_files": multi_file,
            "totals": {
                "total_entries": total_entries,
                "unique_ids": len(unique_ids),
                "duplicate_entries": duplicate_entry_count,
                "ids_appearing_in_multiple_files": len(multi_file),
                "per_file_counts": {k: len(v) for k, v in by_file.items()},
            },
        },
        "x": load_x_unique_count(),
        "fred": load_fred_unique_count(),
    }


def main() -> None:
    evidence = build_evidence()
    out = HERE / "dedup-evidence.json"
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    t = evidence["arxiv"]["totals"]
    print(
        f"Wrote {out.name}: arxiv total={t['total_entries']} "
        f"unique={t['unique_ids']} dupes={t['duplicate_entries']} "
        f"multi-file-ids={t['ids_appearing_in_multiple_files']}; "
        f"x unique={evidence['x']['unique_ids']}; "
        f"fred series={evidence['fred']['series_count']} "
        f"obs={evidence['fred']['total_observations']}"
    )


if __name__ == "__main__":
    main()
