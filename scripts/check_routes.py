import json, math, sys

def dist_km(a, b):
    la1, lo1, la2, lo2 = a[1], a[0], b[1], b[0]
    r = 6371.0
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2 - la1)
    dlam = math.radians(lo2 - lo1)
    aa = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * r * math.asin(math.sqrt(aa))

def fmt(c):
    return "[%.5f,%.5f]" % (c[0], c[1])

d = json.load(open("highway_routes.json"))
print("="*90)
for code in sorted(d.keys()):
    r = d[code]
    coords = r["coords"]
    n = len(coords)
    start_end = dist_km(coords[0], coords[-1]) if n>1 else 0
    max_seg = 0
    max_idx = -1
    for i in range(n-1):
        seg = dist_km(coords[i], coords[i+1])
        if seg > max_seg:
            max_seg = seg
            max_idx = i
    flyovers = [i for i in range(n-1) if dist_km(coords[i], coords[i+1]) > 10.0]
    probs = []
    if start_end > 5.0:
        probs.append("闭环%.1fkm" % start_end)
    if n < 30:
        probs.append("少点(%d)" % n)
    if flyovers:
        probs.append("飞点%d_%.1fkm" % (len(flyovers), max_seg))
    status = "OK" if not probs else "FIX"
    print("%-8s %4d点 首尾%6.1fkm 段距%6.1fkm  [%s]  %s" % (
        code, n, start_end, max_seg, status, ", ".join(probs) if probs else "-"))
    if flyovers and len(flyovers) <= 3:
        for idx in flyovers:
            dd = dist_km(coords[idx], coords[idx+1])
            print("         飞点 [%d]->[%d] %.1fkm: %s -> %s" % (
                idx, idx+1, dd, fmt(coords[idx]), fmt(coords[idx+1])))
print("="*90)
print("\n统计: %d条高速" % len(d))
