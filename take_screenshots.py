import asyncio
from playwright.async_api import async_playwright
import time

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        
        page = await context.new_page()
        await page.goto('http://localhost:5000')
        await page.wait_for_selector('.leaflet-container', timeout=10000)
        
        # Trip Planner Demo
        print("Adding stops for Trip Planner...")
        stops = [
            (28.7041, 77.1025),
            (28.6328, 77.2197),
            (28.5562, 77.1000),
            (28.6139, 77.2090),
            (28.5355, 77.3910)
        ]
        
        for lat, lng in stops:
            await page.evaluate(f"addStop({lat}, {lng}, 'Stop {lat}')")
            await asyncio.sleep(0.2)
            
        print("Optimizing trip...")
        await page.evaluate("runOptimize()")
        await asyncio.sleep(3) # Wait for results to render
        
        # Zoom in and pan to offset the sidebar
        await page.evaluate("map.zoomIn(1); map.panBy([-150, 0])")
        await asyncio.sleep(1)
        
        # Take screenshot
        print("Taking Trip Planner screenshot...")
        await page.screenshot(path='docs/trip_planner_demo.png')
        
        # Now Fleet Optimizer Demo
        print("Switching to Fleet mode...")
        await page.evaluate("switchMode('fleet')")
        
        # We need a few more stops for fleet
        more_stops = [
            (28.4595, 77.0266),
            (28.3949, 77.3114),
            (28.6692, 77.4538)
        ]
        for lat, lng in more_stops:
            await page.evaluate(f"addStop({lat}, {lng}, 'Stop {lat}')")
            await asyncio.sleep(0.2)
            
        print("Optimizing fleet...")
        await page.evaluate("runOptimize()")
        await asyncio.sleep(3) # Wait for results to render
        
        # Zoom in and pan to offset the sidebar
        await page.evaluate("map.zoomIn(1); map.panBy([-150, 0])")
        await asyncio.sleep(1)
        
        print("Taking Fleet Optimizer screenshot...")
        await page.screenshot(path='docs/fleet_optimizer_demo.png')
        
        await browser.close()
        print("Done.")

if __name__ == '__main__':
    asyncio.run(run())
