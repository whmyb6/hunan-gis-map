# 湖南交通地图 - v6

> 湖南高速、铁路、省道 GIS 可视化地图。FastAPI + Leaflet。

## 运行

```bash
cd hunan-gis-map
pip install -r requirements.txt
python main.py        # http://127.0.0.1:8000
```

## 数据规模

| 图层 | 数量 | 数据来源 |
|------|------|----------|
| 地级市 | 14 | 中心坐标 |
| 省界/地市边界 | 14 个真实多边形 | OpenStreetMap GeoJSON |
| 高速路线 | **23 条** | **OSM 真实提取 (via osmium-tool)** |
| 省道 | 8 条 | 部分 OSM + 插值 |
| 铁路 | **10 条线路，~66 个站点** | **OSM 真实曲线** |
| 收费站 | 45 个 | 硬编码坐标 |
| 服务区 | 14 个 | 硬编码坐标 |

## API

| 接口 | 说明 |
|------|------|
| `GET /` | 地图页面 |
| `GET /api/gis-data` | 城市、铁路、收费站、服务区 |
| `GET /api/province-boundary` | 省界 GeoJSON |
| `GET /api/city-boundaries` | 14 个地市边界 |
| `GET /api/highway-routes` | 高速/省道路线坐标 |

## 视图模式

- **全部** (默认)
- **高铁** (虚线黑白标准铁路图式 + 站点)
- **高速** (实线 + 收费站 + 服务区)
- **省道** (含在建虚线)

## OSM 提取流水线

`osmium tags-filter` → 逐 `ref` 提取 → `osmium export` GeoJSON → Python 坐标变换 (lon,lat→lat,lon) + `linemerge` 连通分量筛选 → 下采样 → `highway_routes.py`

提取 23 条高速:
`G4, G0401, G0421, G0422, G5013, G55, G5513, G5515, G56, G59, G60, G6021, G65, G72, G76, S10, S12, S20, S21, S50, S52, S70, S71, S80`

新增：`S12`（黄茅界-八字哨）、扩容 `G5013` 等新提取。

---

速记：
- 数据源：`highway_routes.py` ← OSM 真实
- 双出口问题已解决：`gis_data.json` 中去除 `highways.routes` 冗余
- 截图脚本：`cap.py` 已修正端口 → 8000
- 端口：8000

Author: Hermes Agent v6
