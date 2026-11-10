"""Optional real-network check, isolated from the published analytical snapshot."""
import asyncio
import json
from pathlib import Path

from observatory.collect import Collector, Policy
from observatory.storage import Lake, read_json, write_json


async def main():
    catalog = read_json(Path("data/catalog.json"))
    target = next(t for t in catalog["targets"] if t["group"] == "santander" and t["family"] == "opendata-loans_personal-loans")
    lake = Lake(Path("artifacts/live-smoke/lake"))
    with lake.lock():
        result = await Collector(lake, Policy(concurrency=1, retries=1, timeout=20)).run({"targets": [target], "evidence": catalog["evidence"]})
    capture = result["captures"][0]
    report = {"test": "real_https_verified_collection", "url": target["url"], "meta": capture["meta"],
              "pages": len(capture["objects"]), "bytes": capture["bytes"], "snapshot_id": result["snapshot_id"]}
    write_json(Path("artifacts/live-smoke/result.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return not (capture["meta"]["status"] == 200 and not capture["meta"]["error"])


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
