import asyncio, time, json, sys, os
from playwright.async_api import async_playwright

async def _wait_for_map(page, timeout_ms=30000):
    """等待页面中 map 变量可用"""
    await page.wait_for_function(
        "() => typeof map !== 'undefined' && map !== null",
        timeout=timeout_ms
    )

async def capture(url, js_eval_commands_str, output_path, zoom=7, delay=2):
    """
    通用地图截图函数
    url: 地图页面
    js_eval_commands_str: 分号分隔的JS命令
    output_path: 截图保存路径（Win路径需绝对）
    zoom: 地图zoom等级
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'], headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1200})
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await _wait_for_map(page)
        await page.wait_for_timeout(2000)
        # 设置zoom等级
        if zoom is not None:
            await page.evaluate(f"map.setZoom({zoom});")
        # 执行js命令
        if js_eval_commands_str:
            commands = js_eval_commands_str.split(';')
            for cmd in commands:
                cmd = cmd.strip()
                if cmd:
                    res = await page.evaluate(cmd)
        # 再等tiles和重渲染
        await page.wait_for_timeout(3000)
        for _ in range(5):
            loaded = await page.evaluate("""
                () => {
                    if (typeof map === 'undefined') return false;
                    const tileLayers = [];
                    map.eachLayer(l => { if(l instanceof L.TileLayer) tileLayers.push(l); });
                    return tileLayers.length === 0 || 'canvas' in (tileLayers[0]._container || {});
                }
            """)
            if loaded:
                break
            await asyncio.sleep(1)
        await page.wait_for_timeout(1000)
        # Convert /mnt/c/... to C:/... for Windows
        win_path = output_path
        if win_path.startswith('/mnt/c/'):
            win_path = 'C:/' + win_path[7:]
        await page.screenshot(path=win_path, full_page=False)
        await browser.close()
        print(f"截图完成: {output_path} -> {win_path}")

async def capture_wide_zoomed(url, output_path, zoom=7):
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--no-sandbox', '--disable-setuid-sandbox'], headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1200})
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await _wait_for_map(page)
        # 全图模式加载所有图层 + 设置zoom
        await page.evaluate(f"setViewMode('all'); map.setZoom({zoom});")
        for _ in range(8):
            loaded = await page.evaluate("""() => {
                if (typeof map === 'undefined') return false;
                const t = [];
                map.eachLayer(l => { if(l instanceof L.TileLayer) t.push(l); });
                if(t.length === 0) return true;
                let loaded = 0; let total = 0;
                t.forEach(l => {
                    if(!l._tiles) return;
                    Object.values(l._tiles).forEach(tile => {
                        total++;
                        if(tile.complete || tile.loaded) loaded++;
                    });
                });
                return total === 0 || loaded >= total * 0.8;
            }""")
            if loaded:
                break
            await asyncio.sleep(1)
        await page.wait_for_timeout(3000)
        # Convert /mnt/c/... to C:/...
        win_path = output_path
        if win_path.startswith('/mnt/c/'):
            win_path = 'C:/' + win_path[7:]
        await page.screenshot(path=win_path, full_page=False)
        await browser.close()
        print(f"截图完成: {output_path}")

if __name__ == '__main__':
    # python3 screenshot_map.py [zoom] [url] [js_commands] [output_path]
    zoom = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 7
    url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8002/"
    commands = sys.argv[3] if len(sys.argv) > 3 else "setViewMode('all');"
    output = sys.argv[4] if len(sys.argv) > 4 else "/tmp/hunan-map.png"
    asyncio.run(capture(url, commands, output, zoom))
