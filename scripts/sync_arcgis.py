#!/usr/bin/env python3

from __future__ import annotations

import argparse
import gzip
import json
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://dronegis.caa.gov.tw/server/rest/services"
ROOT = Path(__file__).resolve().parents[1]
LAYERS_FILE = ROOT / "data" / "sources" / "layers.json"
USER_AGENT = "taiwan-drone-caa-data/1.0"
SSL_CONTEXT = ssl._create_unverified_context()
TZ_PLUS8 = timezone(timedelta(hours=8))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Taiwan CAA drone ArcGIS layers")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "data" / "latest"),
        help="Directory for generated data files (default: data/latest)",
    )
    parser.add_argument(
        "--layer",
        help="Only sync a single layer slug",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Delay between paged requests (default: 0.2)",
    )
    parser.add_argument(
        "--compare-manifest",
        help="Path to a previous manifest.json for diff comparison",
    )
    return parser.parse_args()


def load_layers(selected_slug: str | None) -> list[dict[str, Any]]:
    layers = json.loads(LAYERS_FILE.read_text(encoding="utf-8"))
    enabled = [l for l in layers if l.get("enabled", True)]
    if selected_slug:
        enabled = [l for l in enabled if l["slug"] == selected_slug]
        if not enabled:
            raise SystemExit(f"Unknown layer slug: {selected_slug}")
    return enabled


def request_json(url: str, params: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    query = urlencode(params)
    req = Request(f"{url}?{query}", headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=120, context=SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(attempt)
    raise RuntimeError(f"Failed request: {url} ({last_error})")


def get_query_url(service_path: str) -> str:
    return f"{BASE_URL}/{service_path}/query"


def fetch_count(query_url: str) -> int:
    payload = request_json(
        query_url,
        {"where": "1=1", "returnCountOnly": "true", "f": "pjson"},
    )
    return int(payload["count"])


def fetch_geojson_page(query_url: str, offset: int, page_size: int) -> dict[str, Any]:
    payload = request_json(
        query_url,
        {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "orderByFields": "objectid",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "geojson",
        },
    )
    if payload.get("type") != "FeatureCollection":
        raise RuntimeError(f"Unexpected payload from {query_url}")
    return payload


def write_json(path: Path, data: dict[str, Any], *, compact: bool = False) -> None:
    kwargs: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    path.write_text(json.dumps(data, **kwargs) + "\n", encoding="utf-8")


def collect_objectids(geojson: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for feat in geojson.get("features", []):
        oid = feat.get("id")
        if oid is not None:
            ids.add(int(oid))
    return ids


def sync_layer(
    layer: dict[str, Any],
    output_dir: Path,
    sleep_seconds: float,
) -> dict[str, Any]:
    slug = layer["slug"]
    title = layer["title"]
    service = layer["service"]
    page_size = int(layer.get("page_size", 1000))
    query_url = get_query_url(service)
    source_page = f"https://dronegis.caa.gov.tw/server/rest/services/{service}"
    fetched_at = datetime.now(timezone.utc).isoformat()

    count = fetch_count(query_url)
    features: list[dict[str, Any]] = []
    page_count = 0

    for offset in range(0, count, page_size):
        page = fetch_geojson_page(query_url, offset=offset, page_size=page_size)
        features.extend(page.get("features", []))
        page_count += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    feature_collection = {
        "type": "FeatureCollection",
        "name": slug,
        "features": features,
    }

    objectids = collect_objectids(feature_collection)

    metadata = {
        "slug": slug,
        "title": title,
        "service": service,
        "query_url": query_url,
        "source_page": source_page,
        "feature_count": len(features),
        "reported_count": count,
        "objectids": sorted(objectids),
        "page_size": page_size,
        "page_count": page_count,
        "fetched_at": fetched_at,
    }

    write_json(output_dir / f"{slug}.geojson", feature_collection, compact=True)

    geojson_bytes = json.dumps(
        feature_collection, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    gz_path = output_dir / f"{slug}.geojson.gz"
    with gzip.open(gz_path, "wb") as gz:
        gz.write(geojson_bytes)

    write_json(output_dir / f"{slug}.metadata.json", metadata)

    return metadata


def compare_manifests(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    prev_map: dict[str, dict[str, Any]] = {}
    for layer in previous.get("layers", []):
        prev_map[layer["slug"]] = layer

    layers_diff: dict[str, Any] = {}
    has_changes = False
    changed_count = 0

    for cur in current.get("layers", []):
        slug = cur["slug"]
        prev = prev_map.get(slug)
        if prev is None:
            layers_diff[slug] = {
                "previous_count": 0,
                "current_count": cur["feature_count"],
                "added_objectids": cur.get("objectids", []),
                "removed_objectids": [],
                "changed": True,
                "is_new": True,
            }
            has_changes = True
            changed_count += 1
            continue

        cur_ids = set(cur.get("objectids", []))
        prev_ids = set(prev.get("objectids", []))
        added = sorted(cur_ids - prev_ids)
        removed = sorted(prev_ids - cur_ids)
        changed = bool(added or removed)

        layers_diff[slug] = {
            "previous_count": prev["feature_count"],
            "current_count": cur["feature_count"],
            "added_objectids": added,
            "removed_objectids": removed,
            "changed": changed,
            "is_new": False,
        }
        if changed:
            has_changes = True
            changed_count += 1

    return {
        "has_changes": has_changes,
        "changed_layer_count": changed_count,
        "total_layer_count": len(current.get("layers", [])),
        "layers": layers_diff,
    }


def generate_changelog(
    diff: dict[str, Any],
    current_manifest: dict[str, Any],
    output_dir: Path,
) -> Path:
    title_map: dict[str, str] = {}
    for layer in current_manifest.get("layers", []):
        title_map[layer["slug"]] = layer["title"]

    lines: list[str] = ["## 變動摘要", ""]

    changed_layers = []
    unchanged_layers = []

    for slug, info in diff["layers"].items():
        if info["changed"]:
            changed_layers.append((slug, info))
        else:
            unchanged_layers.append(slug)

    for slug, info in changed_layers:
        title = title_map.get(slug, slug)
        lines.append(f"### {slug}（{title}）")
        if info.get("is_new"):
            lines.append(f"- 新圖層，共 {info['current_count']} 筆")
        else:
            prev = info["previous_count"]
            cur = info["current_count"]
            delta = cur - prev
            sign = "+" if delta > 0 else ""
            lines.append(f"- 筆數：{prev} → {cur}（{sign}{delta}）")
            if info["added_objectids"]:
                ids_str = ", ".join(str(i) for i in info["added_objectids"])
                lines.append(f"- 新增 objectid：{ids_str}")
            if info["removed_objectids"]:
                ids_str = ", ".join(str(i) for i in info["removed_objectids"])
                lines.append(f"- 移除 objectid：{ids_str}")
        lines.append("")

    if unchanged_layers:
        lines.append("### 無變動圖層")
        for slug in unchanged_layers:
            title = title_map.get(slug, slug)
            lines.append(f"- {slug}（{title}）")
        lines.append("")

    lines.append("---")
    lines.append(
        f"本次同步共 {diff['total_layer_count']} 個圖層，"
        f"{diff['changed_layer_count']} 個有變動。"
    )

    changelog_path = output_dir / "changelog.md"
    changelog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changelog_path


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    layers = load_layers(args.layer)
    manifest_layers: list[dict[str, Any]] = []

    for layer in layers:
        metadata = sync_layer(
            layer, output_dir=output_dir, sleep_seconds=args.sleep_seconds
        )
        manifest_layers.append(metadata)
        print(f"synced {metadata['slug']}: {metadata['feature_count']} features")

    now_utc = datetime.now(timezone.utc)
    now_taipei = datetime.now(TZ_PLUS8)
    tag = now_taipei.strftime("v%Y.%m.%d-%H%M")

    manifest = {
        "dataset": "taiwan-drone-caa-data",
        "generated_at": now_utc.isoformat(),
        "tag": tag,
        "layer_count": len(manifest_layers),
        "layers": manifest_layers,
    }
    write_json(output_dir / "manifest.json", manifest)

    if args.compare_manifest:
        prev_path = Path(args.compare_manifest)
        if prev_path.exists():
            previous = json.loads(prev_path.read_text(encoding="utf-8"))
            diff = compare_manifests(manifest, previous)
            write_json(output_dir / "diff_report.json", diff)

            if diff["has_changes"]:
                generate_changelog(diff, manifest, output_dir)
                print(
                    f"changes detected: {diff['changed_layer_count']} layer(s) changed"
                )
            else:
                print("no changes detected")
        else:
            print(f"previous manifest not found: {prev_path}")
            layers_diff = {}
            for layer in manifest_layers:
                layers_diff[layer["slug"]] = {
                    "previous_count": 0,
                    "current_count": layer["feature_count"],
                    "added_objectids": layer.get("objectids", []),
                    "removed_objectids": [],
                    "changed": True,
                    "is_new": True,
                }
            diff = {
                "has_changes": True,
                "reason": "no_previous_release",
                "changed_layer_count": len(layers_diff),
                "total_layer_count": len(layers_diff),
                "layers": layers_diff,
            }
            write_json(output_dir / "diff_report.json", diff)
            generate_changelog(diff, manifest, output_dir)
            print("no previous release found, treating as initial release")

    return 0


if __name__ == "__main__":
    sys.exit(main())
