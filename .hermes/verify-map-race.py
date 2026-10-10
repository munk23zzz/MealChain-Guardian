import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel='chrome')
        page = await browser.new_page()
        await page.goto('http://localhost:3000')
        await page.get_by_role('button', name='SPPG Head', exact=True).click()
        await page.get_by_role('button', name='Masuk', exact=True).click()
        await page.get_by_role('heading', name='Peta Kondisi — telur', exact=True).wait_for()
        release = asyncio.Event()
        captured = asyncio.Event()
        async def delayed(route):
            response = await route.fetch()
            captured.set()
            await release.wait()
            await route.fulfill(response=response)
        await page.route('**/balance/map?commodity=ayam', delayed)
        await page.get_by_role('button', name='ayam', exact=True).click()
        await asyncio.wait_for(captured.wait(), 15)
        await page.get_by_role('button', name='wortel', exact=True).click()
        await page.get_by_role('heading', name='Peta Kondisi — wortel', exact=True).wait_for()
        release.set()
        await page.wait_for_timeout(1000)
        heading = await page.locator('.map-card h3').inner_text()
        print(json.dumps({'heading_after_late_response': heading}, ensure_ascii=False))
        await browser.close()
        assert 'wortel' in heading, 'Respons ayam lama mengganti komoditas wortel terpilih'

asyncio.run(main())
