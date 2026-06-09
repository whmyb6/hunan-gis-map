#!/usr/bin/env python3
"""
百度API 多段拼接路线提取 - 针对 G4/G56/G65
分段调用百度 v2 路径规划, 拼接去重, gcj02转wgs84, 替换 highway_routes.json
"""
import requests, json, time, math, sys, os

AK = "zlgnfJ54clZ9wgIdU3VeNqBjKHynXd5g"

x_pi = math.pi * 3000.0 / 180.0
a = 6378245.0
ee = 0.00669342162296594323

def gcj02_to_wgs84(lng, lat):
    """gcj02 (火星坐标) 转 wgs84"""
    def transformlat(lng, lat):
        ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
        ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
        return ret
    def transformlng(lng, lat):
        ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
        ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(lng * math.pi) + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
        return ret
    dlat = transformlat(lng - 105.0, lat - 35.0)
    dlng = transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = dlat * 180.0 / (a / sqrtmagic * math.cos(radlat) * math.pi)
    dlng = dlng * 180.0 / (a / sqrtmagic * math.pi)
    # 反向迭代: wgs + delta -> gcj02, 所以 wgs = gcj02 - delta
    mglat = lat + dlat
    mglng = lng + dlng
    return (lng - (mglng - lng), lat - (mglat - lat))

def dist_km(a, b):
    # a,b = [lon, lat] in wgs84
    la1, lo1, la2, lo2 = a[1], a[0], b[1], b[0]
    r = 6371.0
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2-la1)
    dlam = math.radians(lo2-lo1)
    a2 = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2*r*math.asin(math.sqrt(a2))

def fetch_baidu_segment(origin, destination, ak, tactic=11):
    """百度 v2 驾车路径规划. origin/destination = (lat, lon) wgs84 coordinates."""
    url = "https://api.map.baidu.com/direction/v2/driving"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "tactics": tactic,  # 11=默认路线
        "coord_type": "wgs84",
        "ret_coordtype": "gcj02",
        "ak": ak,
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0"}, timeout=30)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code}, retry {attempt+1}", file=sys.stderr)
                time.sleep(2)
                continue
            data = r.json()
            status = data.get("status", -1)
            if status != 0:
                # 超过配额或key无效
                print(f"  百度返回 status={status} msg={data.get('message','')}, retry {attempt+1}", file=sys.stderr)
                time.sleep(2)
                continue
            result = data["result"]
            routes = result.get("routes", [])
            if not routes:
                print(f"  无路线, retry {attempt+1}", file=sys.stderr)
                time.sleep(1)
                continue
            route = routes[0]
            steps = route.get("steps", [])
            coords = []
            for step in steps:
                path_str = step.get("path", "")
                if not path_str:
                    continue
                for pt_str in path_str.split(";"):
                    if "," not in pt_str:
                        continue
                    lon, lat = map(float, pt_str.split(","))
                    # 转 wgs84
                    wgs_lon, wgs_lat = gcj02_to_wgs84(lon, lat)
                    coords.append([wgs_lon, wgs_lat])
            total_dist = sum(s["distance"] for s in steps)
            return coords, total_dist, len(steps)
        except Exception as exc:
            print(f"  {type(exc).__name__}: {exc}, retry {attempt+1}", file=sys.stderr)
            time.sleep(3)
    return [], -1, 0

# === 控制点定义 (lat, lon) wgs84 ===
# G4 京港澳 - 岳阳→长沙→株洲→湘潭→衡阳→郴州→粤界
G4_WAYPOINTS = [
    (29.55,   113.20),   # 临湘/湖北入口
    (29.367,  113.122),  # 岳阳
    (28.8,    113.0),    # 汨罗
    (28.234,  112.9388), # 长沙
    (27.83,   112.9441), # 湘潭
    (27.65,   112.7),    # 衡山
    (26.9,    112.596),  # 衡阳
    (26.2,    112.55),   # 耒阳
    (25.806,  113.027),  # 郴州
    (25.3,    112.95),   # 宜章
    (24.8,    112.8),    # 广东出口附近
]

# G56 杭瑞 - 江西→平江→岳阳→益(chang城墙)→常德→桃源→张家界→桑植→吉首→凤凰→泸溪→麻阳→芷江→贵州
G56_WAYPOINTS = [
    (29.5,    113.5),    # 江西界
    (29.367,  113.122),  # 岳阳
    (28.574,  112.323),  # 益阳
    (29.032,  111.69),   # 常德
    (29.2,    111.5),    # 桃源
    (29.117,  110.48),   # 张家界
    (29.4,    110.15),   # 桑植
    (28.312,  109.73),   # 吉首/湘西
    (28.1,    109.65),   # 泸溪
    (27.45,   109.68),   # 凤凰
    (27.6,    109.5),    # 麻阳
    (27.444,  109.679),  # 怀化/芷江
    (27.2,    109.4),    # 新晃
    (27.0,    109.2),    # 贵州界
]

# G65 包茂 - 重庆→花垣→吉首→泸溪→凤凰→麻阳→怀化→中方→洪江→会同→靖州→通道→广西
G65_WAYPOINTS = [
    (28.8,    109.2),    # 重庆界
    (28.572,  109.482),  # 花垣
    (28.312,  109.73),   # 吉首
    (28.1,    109.65),   # 泸溪
    (27.7,    109.4),    # 凤凰
    (27.7,    109.3),    # 麻阳
    (27.55,   110.0),    # 怀化
    (27.3,    110.2),    # 中方
    (27.1,    109.9),    # 洪江
    (26.85,   109.7),    # 会同
    (26.5,    109.7),    # 靖州
    (26.2,    109.8),    # 通道
    (25.8,    110.0),    # 广西界
]

def fetch_railway(code, waypoints, ak):
    """分段拼接整条路线, 去重, 返回坐标序列"""
    print(f"\n=== {code}: {len(waypoints)-1} 段 ===", file=sys.stderr)
    all_coords = []
    total_dist = 0
    for i in range(len(waypoints)-1):
        origin = waypoints[i]
        dest = waypoints[i+1]
        print(f"  第{i+1}段: ({origin[0]}, {origin[1]}) → ({dest[0]}, {dest[1]})", file=sys.stderr, end="")
        sys.stderr.flush()
        seg_coords, seg_dist, n_steps = fetch_baidu_segment(origin, dest, ak)
        if not seg_coords:
            print("  [FAIL]", file=sys.stderr)
            continue
        seg_seg_km = sum(dist_km(seg_coords[j], seg_coords[j+1]) for j in range(len(seg_coords)-1))
        # 拼接去重: 如果当前段首点与上一段尾点 <100m, 去首点
        if all_coords and dist_km(all_coords[-1], seg_coords[0]) < 0.1:
            all_coords.extend(seg_coords[1:])
        else:
            all_coords.extend(seg_coords)
        total_dist += seg_dist
        print(f"  [OK] {len(seg_coords)}pts, dist={seg_dist/1000:.1f}km, step_km={seg_seg_km:.1f}km", file=sys.stderr)
        time.sleep(0.3)  # 百度限流友好
    
    if len(all_coords) < 2:
        return all_coords, 0
    
    # 下采样: 如果点太多(>2000), 每隔N个取一个
    max_pts = 1500
    if len(all_coords) > max_pts:
        step = math.ceil(len(all_coords) / max_pts)
        all_coords = [all_coords[i] for i in range(0, len(all_coords), step)]
        print(f"  下采样: {len(all_coords)} 点", file=sys.stderr)
    
    max_seg = max((dist_km(all_coords[j], all_coords[j+1]) for j in range(len(all_coords)-1)), default=0)
    print(f"  总计: {len(all_coords)} 点, 总程={total_dist/1000:.1f}km, 最大段距={max_seg:.2f}km", file=sys.stderr)
    return all_coords, total_dist

def main():
    workdir = os.path.dirname(__file__) or "."
    os.chdir(os.path.normpath(os.path.join(workdir, "..")))
    
    # 备份当前 JSON
    with open("highway_routes.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    with open("highway_routes.json.bak3", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    changes = []
    for code, waypoints in [("G4", G4_WAYPOINTS), ("G56", G56_WAYPOINTS), ("G65", G65_WAYPOINTS)]:
        new_coords, total_dist = fetch_railway(code, waypoints, AK)
        if not new_coords or total_dist <= 0:
            print(f"\n{code}: FAILED, skip.", file=sys.stderr)
            continue
        old_n = len(data[code]["coords"])
        new_n = len(new_coords)
        data[code]["coords"] = new_coords
        changes.append(f"{code}: {old_n} -> {new_n} 点, 百度API {total_dist/1000:.1f}km")
    
    # 保存
    with open("highway_routes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n=== 结果 ===")
    for c in changes:
        print(f"  {c}")
    
    # 运行检查脚本
    print("\n运行质检...", file=sys.stderr)
    os.system("python3 scripts/check_routes.py")

if __name__ == "__main__":
    main()
