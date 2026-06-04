"""湖南省高铁与高速地图 - FastAPI 后端

修改: 使用真实 GeoJSON 边界数据，高速路线改为 JSON 文件 + 热加载
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import json
import os

app = FastAPI(title="湖南省高铁与高速地图")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 加载主数据
data_file = os.path.join(os.path.dirname(__file__), "static", "gis_data.json")
with open(data_file, 'r', encoding='utf-8') as f:
    GIS_DATA = json.load(f)

# 加载真实边界 GeoJSON
GEOJSON_DIR = os.path.join(os.path.dirname(__file__), "geojson")

# 湖南省边界 (省级)
HUNAN_PROVINCE_GEOJSON = None
province_file = os.path.join(GEOJSON_DIR, "hunan_province.json")
if os.path.exists(province_file):
    with open(province_file, 'r', encoding='utf-8') as f:
        HUNAN_PROVINCE_GEOJSON = json.load(f)

# 湖南省下辖地市边界
city_boundaries_file = os.path.join(GEOJSON_DIR, "hunan_full.json")
CITY_BOUNDARIES = None
if os.path.exists(city_boundaries_file):
    with open(city_boundaries_file, 'r', encoding='utf-8') as f:
        CITY_BOUNDARIES = json.load(f)


# ── 高速公路路线（JSON 文件 + 热加载）──
_HW_JSON = os.path.join(os.path.dirname(__file__), "highway_routes.json")
HIGHWAY_ROUTES = {}


def _load_routes():
    """从 JSON 重新加载高速路线。启动时调用一次，reload 端点可再次调用。"""
    global HIGHWAY_ROUTES
    if os.path.exists(_HW_JSON):
        with open(_HW_JSON, 'r', encoding='utf-8') as f:
            HIGHWAY_ROUTES = json.load(f)
    else:
        # Fallback: 兼容旧版 Python 模块
        import importlib.util
        _hw_path = os.path.join(os.path.dirname(__file__), "highway_routes.py")
        if os.path.exists(_hw_path):
            _spec = importlib.util.spec_from_file_location("highway_routes", _hw_path)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            HIGHWAY_ROUTES = _mod.HIGHWAY_ROUTES
        else:
            HIGHWAY_ROUTES = {}


# 启动时加载
_load_routes()


# ── 路由 ──

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/gis-data")
async def get_gis_data():
    """获取湖南省GIS数据（城市、高铁、高速）"""
    return GIS_DATA


@app.get("/api/province-boundary")
async def get_province_boundary():
    """获取湖南省完整省级边界 GeoJSON（真实数据）"""
    if HUNAN_PROVINCE_GEOJSON:
        return HUNAN_PROVINCE_GEOJSON
    return {"type": "Feature", "properties": {"name": "湖南省"}, "geometry": {"type": "Polygon", "coordinates": [[]]}}


@app.get("/api/city-boundaries")
async def get_city_boundaries():
    """获取湖南省地级市真实边界 GeoJSON（真实数据）"""
    if CITY_BOUNDARIES:
        return CITY_BOUNDARIES
    return {"type": "FeatureCollection", "features": []}


@app.get("/api/highway-routes")
async def get_highway_routes():
    """获取高速公路路线坐标"""
    return HIGHWAY_ROUTES


@app.post("/api/reload")
async def reload_highway_routes():
    """热重载高速路线数据（开发调试用）"""
    before = len(HIGHWAY_ROUTES)
    _load_routes()
    after = len(HIGHWAY_ROUTES)
    return {"ok": True, "before": before, "after": after, "routes": list(HIGHWAY_ROUTES.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
