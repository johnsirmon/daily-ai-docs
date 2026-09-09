"""Audit every retained enclosure without downloading complete episodes."""

from __future__ import annotations

import argparse
import concurrent.futures
import xml.etree.ElementTree as ET

import requests


def _check(item: ET.Element) -> tuple[str, str]:
    guid = item.findtext("guid") or "missing-guid"
    enclosure = item.find("enclosure")
    if enclosure is None:
        return guid, "missing enclosure"
    url = enclosure.get("url", "")
    expected = int(enclosure.get("length") or 0)
    try:
        head = requests.head(url, allow_redirects=True, timeout=30)
        if head.status_code != 200:
            return guid, f"HEAD {head.status_code}"
        actual = int(head.headers.get("Content-Length") or 0)
        if actual != expected:
            return guid, f"length {actual} != {expected}"
        ranged = requests.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=30)
        if ranged.status_code != 206:
            return guid, f"range {ranged.status_code}"
        return guid, "ok"
    except Exception as exc:
        return guid, f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", default="podcast.xml")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    items = ET.parse(args.feed).findall(".//item")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(_check, items))
    failures = [(guid, status) for guid, status in results if status != "ok"]
    print(f"checked {len(results)} enclosure(s); failures={len(failures)}")
    for guid, status in failures:
        print(f"{guid}: {status}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
