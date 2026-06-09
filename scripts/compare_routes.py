import json
import sys, math

def dist_km(a, b):
    la1, lo1, la2, lo2 = a[1], a[0], b[1], b[0]
    r = 6371.0
    phi1, phi2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2-la1)
    dlam = math.radians(lo2-lo1)
    a2 = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2*r*math.asin(math.sqrt(a2))

# 加载 py 数据
with open("highway_routes.py") as f:
    code = f.read()
exec(code)
d_py = HIGHWAY_ROUTES

# 加载 json 数据
with open("highway_routes.json") as f:
    d_json = json.load(f)

print("对比:        PY点数 JSON点数  PY最大段距 JSON最大段距 PY首尾距 JSON首尾距")
for code in sorted(d_py.keys()):
    py_coords = d_py[code]["coords"]
    j_coords = d_json[code]["coords"]
    
    c_py = len(py_coords)
    c_j = len(j_coords)
    
    # json 的段距
    max_seg_j = max(dist_km(j_coords[i], j_coords[i+1]) for i in range(c_j-1)) if c_j>1 else 0
    max_seg_p = max(dist_km(py_coords[i], py_coords[i+1]) for i in range(c_py-1)) if c_py>1 else 0
    
    se_p = dist_km(py_coords[0], py_coords[-1]) if c_py>1 else 0
    se_j = dist_km(j_coords[0], j_coords[-1]) if c_j>1 else 0
    
    # 同一点与否
    first_diff = dist_km(py_coords[0], j_coords[0]) if c_py>0 and c_j>0 else 999
    
    mark = ""
    if max_seg_j > max_seg_p and max_seg_j > 5:
        mark = "[JSON更粗 需补]"
    elif c_j < c_py * 0.5:
        mark = "[JSON点极少 需补]"
    
    print(f"{code:<8}  {c_py:>5}    {c_j:>5}      {max_seg_p:5.1f}      {max_seg_j:5.1f}       {se_p:5.1f}    {se_j:5.1f}   {mark}")
