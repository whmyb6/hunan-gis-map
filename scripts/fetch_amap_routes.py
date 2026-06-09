#!/usr/bin/env python3
"""
fetch_amap_routes.py - 使用高德API (Amap) 获取高速路线轨迹坐标
数据格式说明: 高德坐标系为 GCJ-02 (与 WGS-84 有约 100~300m 偏移)
"""
import json
import os
import time
import requests

GAODE_KEY = "84ad58c08d8606cbae62e36be1e8f0d8"
BASE_URL = "https://restapi.amap.com/v3/direction/driving"

PROJECT_DIR = "/mnt/c/Users/user_l2B5jGl5k/Desktop/源代码/hunan-gis-map"


# 高德 API: origin/destination/waypoints = 经度,纬度 (lon,lat)
# 项目坐标: [纬度, 经度] (lat,lon)
# 本脚本内部转换

AMAP_ROUTES = {
    # 分段时间距控制在 80-120km 以内，避免高德 API 截断或改道
    "S80": {
        "name": "衡邵高速",
        "segments": [
            [27.492, 112.621],   # 衡阳 暖水亭互通
            [27.47, 112.45],     # 衡阳县
            [27.26, 111.75],     # 邵东
            [27.14, 111.47],     # 邵阳
        ]
    },
    "G5013": {
        "name": "渝长高速",
        "segments": [
            [30.000, 108.900],   # 重庆西界
            [30.120, 109.230],
            [29.950, 109.920],
            [29.720, 110.150],
            [29.560, 111.520],   # 长沙方向
        ]
    },
    "G59": {
        "name": "呼北高速",
        "segments": [
            [29.9, 111.0],       # 石门北 (北端)
            [29.55, 111.38],     # 慈利
            [29.35, 110.45],     # 张家界
            [29.05, 111.15],     # 常德
            [28.8, 111.55],      # 南端 (参考，可调整)
        ]
    },
}


def get_route_segment(start_lat, start_lon, end_lat, end_lon, retries=2):
    """高德 v3 路径规划，origin/destination 用 经度,纬度"""
    origin = f"{start_lon},{start_lat}"
    destination = f"{end_lon},{end_lat}"
    params = {
        "key": GAODE_KEY,
        "origin": origin,
        "destination": destination,
        "extensions": "all",
        "strategy": "0",     # 速度优先（默认走高速）
        "output": "json",
    }
    for attempt in range(retries + 1):
        try:
            r = requests.get(BASE_URL, params=params, timeout=15)
            data = r.json()
        except Exception as e:
            print(f"    [ERR net] {e}, retry {attempt + 1}/{retries + 1}")
            time.sleep(1)
            continue

        status = data.get("status")
        if status == "1":
            route = data.get("route", {})
            paths = route.get("paths", [])
            if not paths:
                return None
            steps = paths[0].get("steps", [])
            if not steps:
                return None
            # 解析 polyline: "lon,lat;lon,lat;..."
            points = []
            for step in steps:
                poly = step.get("polyline", "")
                if not poly:
                    continue
                pairs = poly.split(";")
                for pair in pairs:
                    coords = pair.split(",")
                    if len(coords) == 2:
                        try:
                            lon = float(coords[0])
                            lat = float(coords[1])
                            # 转为项目标准 [lat, lon]
                            points.append([lat, lon])
                        except ValueError:
                            pass
            return points
        else:
            info = data.get("info", "unknown")
            print(f"    [ERR] status={status}, info={info}, origin={origin}")
            if "KEY" in str(info).upper() or "Licensed" in str(info):
                return "KEY_ERROR"
            time.sleep(1)
    return None


def get_route(segments, route_name=""):
    """分段采集，拼接整条路线"""
    total = []
    for i in range(len(segments) - 1):
        s_lat, s_lon = segments[i]
        e_lat, e_lon = segments[i + 1]
        print(f"  第{i+1}段: ({s_lat},{s_lon}) -> ({e_lat},{e_lon})")
        pts = get_route_segment(s_lat, s_lon, e_lat, e_lon)
        if pts == "KEY_ERROR":
            print("    -> KEY 失效/受限，终止")
            return None
        if pts is None:
            print("    -> 返回空数据")
            return None
        print(f"    -> 返回 {len(pts)} 点")
        if total:
            # 去重首尾点
            if pts[0] == total[-1]:
                total.extend(pts[1:])
            else:
                total.extend(pts)
        else:
            total.extend(pts)
        time.sleep(0.3)
    return total


def save_route_to_project(route_id, route_name, coords):
    """写入 highway_routes.json"""
    json_path = os.path.join(PROJECT_DIR, "highway_routes.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data[route_id] = {
        "id": route_id,
        "name": route_name,
        "coords": coords,
        "source": "amap",
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"  [OK] highway_routes.json 已更新 ({route_id})")


def main():
    print("=" * 50)
    print(" 高德地图API - 高速路线采集")
    print("=" * 50)
    for route_id, cfg in AMAP_ROUTES.items():
        print(f"\n{route_id} ({cfg['name']}) 开始采集...")
        coords = get_route(cfg["segments"], cfg["name"])
        if coords and len(coords) > 10:
            # 计算均距
            total_km = 0
            max_step = 0
            for i in range(len(coords) - 1):
                import math
                lat1, lon1 = coords[i]
                lat2, lon2 = coords[i + 1]
                R = 6371.0
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = (math.sin(dlat / 2) ** 2 +
                     math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
                d = 2 * R * math.asin(math.sqrt(a))
                total_km += d
                if d > max_step:
                    max_step = d
            avg_step = total_km / (len(coords) - 1) if len(coords) > 1 else 0
            print(f"  汇总: {len(coords)} 点, 总里程约 {total_km:.1f}km, 均距 {avg_step:.3f}km, 最大段 {max_step:.2f}km")
            save_route_to_project(route_id, cfg["name"], coords)
        else:
            print(f"  [SKIP] {route_id} 采集失败或点数不足")
    print("\n全部完成。")


if __name__ == "__main__":
    main()
