#!/usr/bin/env python3
"""
OSM 关系/way 级提取试验 - 针对 G4/G56/G65 三条低质量高速
策略: 用 name 标签+ref 标签双重匹配, 大区域, 端点 linemerge
"""

import os, sys, requests, json, time, math
from collections import defaultdict

os.environ.setdefault("HTTP_PROXY", "http://172.27.64.1:10808")
os.environ.setdefault("HTTPS_PROXY", "http://172.27.64.1:10808")
PROXY = {"http": "http://172.27.64.1:10808", "https": "http://172.27.64.1:10808"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; highway-mapper/2.0)"}

BBOX = (24.0, 108.0, 31.0, 115.0)

TARGETS = {
    "G4":  {"京港澳", "京港澳高速", "G4"},
    "G56": {"杭瑞", "杭瑞高速", "G56"},
    "G65": {"包茂", "包茂高速", "G65"},
}

def dist_km(a, b):
    # a,b = [lon,lat]
    la1, lo1, la2, lo2 = a[1], a[0], b[1], b[0]
    r = 6371.0
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2-la1)
    dlam = math.radians(lo2-lo1)
    a2 = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2*r*math.asin(math.sqrt(a2))

def query_by_name_regex(s, w, n, e, name_patterns, timeout=250):
    """用 Overpass 正则匹配 name/ref 提取特定高速的 way+geometry"""
    # 构建正则: 京港澳|杭瑞|包茂|G4|G56|G65
    name_re = "|".join(name_patterns)
    ql = f"""
[out:json][timeout:200];
(
  way["highway"~"motorway|trunk"]["name"~"{name_re}"]({s},{w},{n},{e});
  way["highway"~"motorway|trunk"]["ref"~"{name_re}"]({s},{w},{n},{e});
);
out body;
>;
out geom;
"""
    for attempt in range(3):
        try:
            r = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": ql},
                proxies=PROXY,
                headers=HEADERS,
                timeout=timeout
            )
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code}, retry {attempt+1}", file=sys.stderr)
            time.sleep(15 if r.status_code == 429 else 8)
        except Exception as exc:
            print(f"  {type(exc).__name__}: {exc}, retry {attempt+1}", file=sys.stderr)
            time.sleep(12)
    return None

def classify_ways(elements):
    """把 way 按 name/ref 匹配分到 G4/G56/G65"""
    groups = defaultdict(list)
    name_counts = defaultdict(int)
    ref_counts = defaultdict(int)
    
    for el in elements:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {})
        name = str(tags.get("name", ""))
        ref = str(tags.get("ref", ""))
        geom = el.get("geometry", [])
        coords = [(round(pt["lon"],6), round(pt["lat"],6)) for pt in geom]
        if len(coords) < 2:
            continue
        
        if name: name_counts[name] += 1
        if ref: ref_counts[ref] += 1
        
        matched = False
        # 先 name 匹配
        for code, keywords in TARGETS.items():
            if any(kw in name for kw in keywords):
                groups[code].append({"id": el["id"], "coords": coords, "name": name, "ref": ref})
                matched = True
                break
        if matched:
            continue
        # 再 ref 匹配
        for code, keywords in TARGETS.items():
            if any(kw in ref for kw in keywords):
                groups[code].append({"id": el["id"], "coords": coords, "name": name, "ref": ref})
                break
    return groups, dict(name_counts), dict(ref_counts)

def greedy_linemerge(ways, snap_km=1.0):
    """贪婪端点匹配, 返回最长连通链的坐标序列"""
    if not ways:
        return []
    
    segs = []
    for w in ways:
        c = w["coords"]
        segs.append({"coords": c, "head": c[0], "tail": c[-1], "used": False, "id": w["id"]})
    
    n = len(segs)
    # 建邻接表
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            # 四种连接距离
            d_hh = dist_km(segs[i]["head"], segs[j]["head"])
            d_ht = dist_km(segs[i]["head"], segs[j]["tail"])
            d_th = dist_km(segs[i]["tail"], segs[j]["head"])
            d_tt = dist_km(segs[i]["tail"], segs[j]["tail"])
            mind = min(d_hh, d_ht, d_th, d_tt)
            if mind <= snap_km:
                adj[i].append((j, mind, d_hh, d_ht, d_th, d_tt))
                adj[j].append((i, mind, d_hh, d_ht, d_th, d_tt))
    
    # 找连通分量 (无向图)
    visited = [False]*n
    components = []
    for i in range(n):
        if visited[i]:
            continue
        comp = [i]
        q = [i]
        visited[i] = True
        while q:
            u = q.pop()
            for v, *_ in adj[u]:
                if not visited[v]:
                    visited[v] = True
                    q.append(v)
                    comp.append(v)
        components.append(comp)
    
    def order_component(comp):
        if len(comp) == 1:
            return segs[comp[0]]["coords"]
        comp_set = set(comp)
        # 找度<=1的端点
        deg = {idx: len([v for v, *_ in adj[idx] if v in comp_set]) for idx in comp}
        ends = [idx for idx in comp if deg[idx] <= 1]
        
        if ends:
            current = ends[0]
        else:
            current = comp[0]
        
        # 确定起始方向
        nbrs = [v for v, *_ in adj[current] if v in comp_set]
        direction = 1
        if nbrs:
            nbr = nbrs[0]
            # 检查当前尾对邻居头
            if dist_km(segs[current]["tail"], segs[nbr]["head"]) <= snap_km:
                direction = 1
            elif dist_km(segs[current]["tail"], segs[nbr]["tail"]) <= snap_km:
                direction = 1  # 尾接尾, 后面会翻转邻居
            else:
                direction = -1  # 头接头或头接尾, 翻转自己
        
        used = {current}
        if direction == -1:
            result = list(reversed(segs[current]["coords"]))
            cur_end = segs[current]["head"]
        else:
            result = list(segs[current]["coords"])
            cur_end = segs[current]["tail"]
        
        # 贪婪扩展
        while True:
            best = None
            best_dist = float('inf')
            best_flip = False
            for v, mind, d_hh, d_ht, d_th, d_tt in adj[current]:
                if v in used or v not in comp_set:
                    continue
                if dist_km(cur_end, segs[v]["head"]) <= snap_km and dist_km(cur_end, segs[v]["head"]) < best_dist:
                    best = v; best_dist = dist_km(cur_end, segs[v]["head"]); best_flip = False
                if dist_km(cur_end, segs[v]["tail"]) <= snap_km and dist_km(cur_end, segs[v]["tail"]) < best_dist:
                    best = v; best_dist = dist_km(cur_end, segs[v]["tail"]); best_flip = True
            if best is None:
                # 断开了,找 comp 内最近的未用邻居(通过其他段)
                found = False
                for possible in comp:
                    if possible in used:
                        continue
                    # 找已用段与它的连接
                    for v, *_ in adj[possible]:
                        if v in used and v in comp_set:
                            # 连接到 used 集合的某个段
                            # 尝试找到连接点
                            pass
                    # 简化: 没有直接连通邻居就停止
                    break
                if not found:
                    break
            
            used.add(best)
            current = best
            if best_flip:
                result.extend(reversed(segs[best]["coords"]))
                cur_end = segs[best]["head"]
            else:
                result.extend(segs[best]["coords"])
                cur_end = segs[best]["tail"]
            
            if len(used) == len(comp):
                break
        
        return result
    
    chains = []
    for comp in components:
        chain = order_component(comp)
        chains.append(chain)
    chains.sort(key=len, reverse=True)
    
    return chains[0] if chains else []

def main():
    s, w, n, e = BBOX
    all_patterns = set()
    for kws in TARGETS.values():
        all_patterns.update(kws)
    patterns = "|".join(sorted(all_patterns))
    
    print(f"Overpass query: bbox ({s},{w},{n},{e}), name/ref ~ {patterns}", file=sys.stderr)
    t0 = time.time()
    data = query_by_name_regex(s, w, n, e, patterns)
    dt = time.time() - t0
    
    if data is None:
        print("OVERPASS FAILED after 3 attempts. Exit.", file=sys.stderr)
        sys.exit(1)
    
    elements = data.get("elements", [])
    ways_count = sum(1 for e in elements if e.get("type")=="way")
    print(f"Response in {dt:.0f}s: {len(elements)} elements, {ways_count} ways", file=sys.stderr)
    
    groups, name_counts, ref_counts = classify_ways(elements)
    
    print("\nMatched name distribution:", file=sys.stderr)
    for name, c in sorted(name_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  name: {name!r}: {c}", file=sys.stderr)
    print("Matched ref distribution:", file=sys.stderr)
    for ref, c in sorted(ref_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  ref: {ref!r}: {c}", file=sys.stderr)
    
    result = {}
    for code in sorted(TARGETS.keys()):
        ways = groups.get(code, [])
        if not ways:
            print(f"\n{code}: NO WAYS FOUND", file=sys.stderr)
            continue
        print(f"\n{code}: {len(ways)} raw ways, linemerging...", file=sys.stderr)
        chain = greedy_linemerge(ways, snap_km=1.0)
        n_pts = len(chain)
        max_seg = max((dist_km(chain[i], chain[i+1]) for i in range(n_pts-1)), default=0)
        
        result[code] = {
            "code": code,
            "coords": chain,
            "points": n_pts,
            "max_segment_km": round(max_seg, 2),
        }
        print(f"  -> merged {n_pts} points, max segment {max_seg:.2f}km", file=sys.stderr)
    
    out = "/tmp/hw_g4g56g65_experiment.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 简洁表格式输出到 stdout
    summary = {k: {"points": v["points"], "max_seg_km": v["max_segment_km"]} for k,v in result.items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nFull data: {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
