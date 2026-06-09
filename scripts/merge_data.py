#!/usr/bin/env python3
"""
补数据脚本：把 highway_routes.py 的完整坐标合并到 highway_routes.json
保留 JSON 中已比 PY 更优的路线，用 PY 补充被严重删减的路线。
"""

import json
import math

def dist_km(a, b):
    la1, lo1, la2, lo2 = a[1], a[0], b[1], b[0]
    r = 6371.0
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2-la1)
    dlam = math.radians(lo2-lo1)
    a2 = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2*r*math.asin(math.sqrt(a2))

def densify(coords, target_max_km=3.0):
    """在线段上均匀插值，使最大段距不超过 target_max_km"""
    if len(coords) < 2:
        return coords
    out = [coords[0]]
    for i in range(len(coords)-1):
        a, b = coords[i], coords[i+1]
        d = dist_km(a, b)
        if d > target_max_km:
            # 插多少个点
            n = int(math.ceil(d / target_max_km))
            for j in range(1, n):
                t = j / n
                lon = a[0] + (b[0]-a[0]) * t
                lat = a[1] + (b[1]-a[1]) * t
                out.append([lon, lat])
        out.append(b)
    return out

# 加载 py 数据
# 在干净 namespace 中执行以提取 HIGHWAY_ROUTES
namespace = {}
with open("highway_routes.py") as f:
    exec(compile(f.read(), "highway_routes.py", "exec"), namespace)

d_py = namespace["HIGHWAY_ROUTES"]

with open("highway_routes.json") as f:
    d_json = json.load(f)

# 备份
with open("highway_routes.json.bak", "w", encoding="utf-8") as f:
    json.dump(d_json, f, ensure_ascii=False, indent=2)

changes = []
for code in sorted(d_json.keys()):
    j = d_json[code]
    if code not in d_py or code not in d_json:
        continue
    py_coords = d_py[code]["coords"]
    j_coords = j["coords"]
    py_n = len(py_coords)
    j_n = len(j_coords)
    
    # 策略：如果 PY 点数 >= 2x 且 PY>=50，用 PY 数据(带插密化)
    # 或者如果 JSON 点数 < 40 但 PY 更优
    use_py = False
    if py_n >= j_n * 2 and py_n >= 50:
        use_py = True
    elif j_n < 40 and py_n > j_n:
        use_py = True
    
    if use_py:
        new_coords = densify(py_coords, 3.0)
        old_n = j_n
        new_n = len(new_coords)
        j["coords"] = new_coords
        changes.append(f"{code}: {old_n} -> {new_n} (from PY, densified)")
    else:
        # 对 JSON 自身进行插密化，如果段距过大
        j_dens = densify(j_coords, 5.0)
        if len(j_dens) != j_n:
            changes.append(f"{code}: {j_n} -> {len(j_dens)} (JSON 插密化)")
            j["coords"] = j_dens

# 保存
with open("highway_routes.json", "w", encoding="utf-8") as f:
    json.dump(d_json, f, ensure_ascii=False, indent=2)

print("已更新 highway_routes.json")
for c in changes:
    print(f"  {c}")
print(f"\n改动 {len(changes)} 条")
