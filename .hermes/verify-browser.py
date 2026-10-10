from playwright.sync_api import sync_playwright
import json
from pathlib import Path

out = Path('D:/Projects/Mealchain/.hermes/browser-evidence')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome')
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://localhost:3000', wait_until='networkidle')
    print(json.dumps({'title': page.title(), 'inputs': page.locator('input').count(), 'errors': errors}))
    page.get_by_role('button', name='SPPG Head', exact=True).click()
    page.get_by_role('button', name='Masuk', exact=True).click()
    page.get_by_role('button', name='Keluar', exact=True).wait_for(timeout=30000)
    page.locator('.map-row').first.wait_for(timeout=30000)
    page.screenshot(path=str(out/'overview-initial.png'), full_page=True)
    print(json.dumps({'rows': page.locator('.map-row').count(), 'errors': errors, 'body': page.locator('body').inner_text()[:2500]}, ensure_ascii=False))
    browser.close()
