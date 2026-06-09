import ast
# 解析 .py 文件
with open("/mnt/c/Users/user_l2B5jGl5k/Desktop/源代码/hunan-gis-map/highway_routes.py") as f:
    content = f.read()
# 提取字典
d = ast.literal_eval(content.split("= ", 1)[1].split("\n", 1)[0].strip())
for code in sorted(d.keys()):
    n = len(d[code]["coords"])
    print(f"{code}: {n} 点")
