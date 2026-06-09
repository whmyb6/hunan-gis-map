import asyncio
from playwright.async_api import async_playwright

async def main():
    url = "http://172.27.72.135:8000/"
    output = "C:/Users/user_l2B5jGl5k/Desktop/截图/after_fix.png"
    cmd = "setViewMode('all');map.setZoom(6);"
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = await browser.new_page(viewport={'width': 1920, 'height': 1200})
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_function(
            "() => typeof map !== 'undefined' && map !== null",
            timeout=30000)
        await page.wait_for_timeout(3000)
        for c in cmd.split(';'):
            c = c.strip()
            if c:
                await page.evaluate(c)
        # 等待 tiles 加载稳定
        for _ in range(10):
            loaded = await page.evaluate("""
                () => {
                    const tl=[];
                    map.eachLayer(l => { if(l instanceof L.TileLayer) tl.push(l); });
                    if(tl.length===0) return true;
                    let ok=0,total=0;
                    tl.forEach(l => {
                        if(!l._tiles) return;
                        Object.values(l._tiles).forEach(t => { total++; if(t.complete || t.loaded) ok++; });
                    });
                    return total===0 || ok >= total*0.8;
                }
            """)
            if loaded:
                break
            await asyncio.sleep(1)
        await page.wait_for_timeout(2000)
        await page.screenshot(path=output, full_page=False)
        print(f"截图完成: {output}")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
