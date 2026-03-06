import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Navigating to login page...")
        await page.goto('http://127.0.0.1:8000/auth/login/')
        await page.wait_for_timeout(2000)

        await page.fill('input[name="username"]', 'admin')
        await page.fill('input[name="password"]', 'admin')

        await page.evaluate("""() => {
            document.querySelector('button[type="submit"]').click();
        }""")

        await page.wait_for_timeout(3000)
        print("Logged in successfully.")

        print("Taking Analytics Screenshot...")
        await page.goto('http://127.0.0.1:8000/canteen/analytics/')
        await page.wait_for_timeout(3000)
        await page.screenshot(path='/home/jules/verification/analytics_updated.png', full_page=True)

        print("Taking Advanced Analytics Screenshot...")
        await page.goto('http://127.0.0.1:8000/canteen/analytics/advanced/')
        await page.wait_for_timeout(3000)
        await page.screenshot(path='/home/jules/verification/advanced_analytics_updated.png', full_page=True)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
