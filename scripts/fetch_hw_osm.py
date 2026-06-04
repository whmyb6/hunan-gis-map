import os
os.environ.setdefault("HTTP_PROXY", "http://172.27.64.1:10808")
os.environ.setdefault("HTTPS_PROXY", "http://172.27.64.1:10808")

import sys, json, time, requests

PROXY = {"http": "http://172.27.64.1:10808", "https": "http://172.27.64.1:10808"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; highway-mapper/1.0)"}

TARGET_REFS = {"G4", "G0401", "G0421", "G0422", "G5013", "G55", "G5513", "G5515", "G56", "G59", "G60", "G6021", "G65", "G72", "G76", "S10", "S20", "S21", "S50", "S52", "S70", "S71", "S80"}

def query_block(s, w, n, e):
    ql = f"""[out:json][timeout:120];
(
  way["highway"~"motorway|trunk"]({s},{w},{n},{e});
);
out geom;"""
    for attempt in range(3):
        try:
            r = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": ql},
                proxies=PROXY,
                headers=HEADERS,
                timeout=160
            )
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code}, retry {attempt+1}", file=sys.stderr)
            time.sleep(15 if r.status_code == 429 else 5)
        except Exception as exc:
            print(f"  {type(exc).__name__}: {exc}, retry {attempt+1}", file=sys.stderr)
            time.sleep(8)
    return None

def main():
    # 1x1 degree blocks for 24.0-30.5 x 108.0-114.5 roughly covers Hunan + border
    blocks = []
    for lat in range(24, 30):
        for lon in range(108, 114):
            blocks.append((float(lat), float(lon), float(lat+1), float(lon+1)))
    print(f"Total {len(blocks)} blocks to fetch", file=sys.stderr)

    ways = []
    for i, (s, w, n, e) in enumerate(blocks):
        print(f"[{i+1}/{len(blocks)}] block {s},{w},{n},{e}", file=sys.stderr)
        t0 = time.time()
        data = query_block(s, w, n, e)
        dt = time.time() - t0
        if data is None:
            print(f"  -> FAILED after {dt:.0f}s", file=sys.stderr)
            continue
        block_ways = 0
        for el in data.get("elements", []):
            if el.get("type") != "way":
                continue
            g = el.get("geometry", [])
            coords = [(round(pt["lat"],6), round(pt["lon"],6)) for pt in g]
            if len(coords) < 2:
                continue
            ways.append({
                "id": el.get("id"),
                "ref": str(el.get("tags", {}).get("ref", "")),
                "name": str(el.get("tags", {}).get("name", "")),
                "highway": str(el.get("tags", {}).get("highway", "")),
                "coords": coords
            })
            block_ways += 1
        print(f"  -> {block_ways} ways in {dt:.1f}s", file=sys.stderr)
        # slight rate limiting only if query was fast (empty blocks)
        if dt < 3:
            time.sleep(0.5)

    print(f"\nTotal ways collected: {len(ways)}", file=sys.stderr)
    with open("/tmp/hw_raw.json", "w", encoding="utf-8") as f:
        json.dump(ways, f, ensure_ascii=False, indent=1)
    print("Saved to /tmp/hw_raw.json", file=sys.stderr)

    c = {}
    for w in ways:
        for t in TARGET_REFS:
            if t in w["ref"]:
                c[t] = c.get(t, 0) + 1
    print("Ref counts:")
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
