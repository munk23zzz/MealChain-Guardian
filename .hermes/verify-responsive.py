import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).parent / 'browser-evidence'
out.mkdir(exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome')
    for role in ['SPPG Head', 'Nutritionist', 'BGN Monitor']:
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://localhost:3000')
        page.get_by_role('button', name=role, exact=True).click()
        page.get_by_role('button', name='Masuk', exact=True).click()
        page.locator('.map-row').first.wait_for(timeout=60000)
        for width in [375, 768, 1440]:
            page.set_viewport_size({'width': width, 'height': 1000})
            page.locator('[data-location-row]').first.wait_for()
            page.screenshot(path=str(out / f'{role.replace(" ", "-").lower()}-{width}.png'), full_page=True)
            metrics = page.evaluate('''() => ({width: innerWidth, documentWidth: document.documentElement.scrollWidth, rows: document.querySelectorAll('[data-location-row]').length})''')
            assert metrics['rows'] == 10, metrics
            results.append({'role': role, **metrics, 'errors': list(errors)})
        if role == 'BGN Monitor':
            assert page.get_by_role('button', name='Demo Control', exact=True).count() == 0
        page.close()
    browser.close()
(out / 'responsive-results.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results))
assert all(row['documentWidth'] <= row['width'] for row in results), 'horizontal overflow'
assert all(not row['errors'] for row in results), 'browser errors'
