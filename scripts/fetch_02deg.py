import os
# Direct, no proxy
os.environ["HTTP_PROXY"]=""
os.environ["HTTPS_PROXY"]=""

import osmnx as ox, geopandas as gpd, pandas as pd, time, json, sys

ox.settings.timeout = 25
# 0.2 degree ~ 22x20km, well within query limits
step = 0.2
lat_start, lat_end = 24.4, 30.6
lon_start, lon_end = 108.4, 114.6

blocks = []
lat = lat_start
while lat < lat_end:
    lon = lon_start
    while lon < lon_end:
        blocks.append((round(lon,2), round(lat,2), round(lon+step,2), round(lat+step,2)))
        lon += step
    lat += step

print(f"直接直连 0.2度区块 {len(blocks)} 块，开跑。", file=sys.stderr)

all_gdfs = []
for i, (left, bottom, right, top) in enumerate(blocks):
    t0 = time.time()
    try:
        gdf = ox.features.features_from_bbox(
            (left, bottom, right, top),
            tags={"highway": ["motorway", "motorway_link", "trunk", "trunk_link"]}
        )
        dt = time.time() - t0
        n = len(gdf)
        if n > 0:
            all_gdfs.append(gdf)
        # 每3块显示一次，减少刷屏
        if i % 3 == 0 or n > 0:
            if n > 0:
                print(f"[{i+1}/{len(blocks)}] {left},{bottom} -> {n} ways in {dt:.1f}s", file=sys.stderr)
            else:
                # 只打印非零或者直接简短打印
                pass
        # 0.5s 限流
        if dt < 2: time.sleep(0.5)
    except Exception as e:
        if "timeout" in str(e).lower() or "Max retries" in str(e):
            print(f"[{i+1}/{len(blocks)}] TIMEOUT, 跳过重试。", file=sys.stderr)
        else:
            print(f"[{i+1}/{len(blocks)}] ERR: {e}", file=sys.stderr)
        time.sleep(1.5)
        continue

print(f"\n收集到 {len(all_gdfs)} 非空区块", file=sys.stderr)
if not all_gdfs:
    print("无数据。\n", file=sys.stderr)
    sys.exit(1)

merged = pd.concat(all_gdfs, ignore_index=True)
print(f"合并后 {len(merged)} 条 feature", file=sys.stderr)

# 粗过滤：centroid 在 108.5-114.4, 24.5-30.4
print("粗过滤只保留湖南中心区内...", file=sys.stderr)
merged = merged.to_crs("EPSG:4326")
cx = merged.centroid.x; cy = merged.centroid.y
merged = merged[cx.between(108.5, 114.4) & cy.between(24.5, 30.4)]
print(f"过滤后 {len(merged)} 条。", file=sys.stderr)

# 按 ref 分组
targets = [
  "G4","G0401","G0421","G0422","G5013","G55","G5513","G5515","G56","G59","G60","G6021","G65","G72","G76",
  "S10","S20","S21","S50","S52","S70","S71","S80"
]

# Build index
groups = {t: [] for t in targets}
for _, row in merged.iterrows():
    ref_s = str(row.get("ref", "")).strip()
    for t in targets:
        if t in ref_s:
            groups[t].append(row)

# Save per ref
for t, rows in groups.items():
    if not rows: continue
    # Note: G55/5513 等别名问题、不需要合并。解决后统一取样
    with open(f"/tmp/geo_{t}.geojson_wkt", "w") as f:
        f.write(str(rows[0].geometry))
    # 为了最终合并，先保存序列化的 GeoJSON
    sub = gpd.GeoDataFrame(rows, columns=merged.columns, crs=merged.crs)
    sub.to_file(f"/tmp/hw_{t}_raw.geojson", driver='GeoJSON')
    print(f"{t}: {len(rows)} ways")

# Save merge
merged.to_file("/tmp/hunan_hw_merged_raw.geojson", driver='GeoJSON')
print("\n保存 /tmp/hunan_hw_merged_raw.geojson 成功。", file=sys.stderr)
