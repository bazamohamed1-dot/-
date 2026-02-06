from playwright.sync_api import sync_playwright
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Verify Login Page
    print("Navigating to login...")
    try:
        page.goto("http://localhost:8000/login/")
    except Exception as e:
        print(f"Failed to load page: {e}")
        return

    page.wait_for_selector("input[name='username']")
    time.sleep(1)

    # 2. Login as Director
    print("Logging in...")
    page.fill("input[name='username']", "director")
    page.fill("input[name='password']", "123456")
    page.click("button[type='submit']")

    try:
        page.wait_for_url("**/dashboard/", timeout=5000)
        print("Logged in as Director.")
    except Exception as e:
        print(f"Login failed or didn't redirect: {e}")

    # 3. Go to Settings
    print("Navigating to settings...")
    page.goto("http://localhost:8000/settings/")
    try:
        page.wait_for_selector("table", timeout=5000)
        page.screenshot(path="settings_page_full.png", full_page=True)
        print("Settings page full screenshot taken.")
    except:
        print("Settings table not found")
        page.screenshot(path="settings_fail.png", full_page=True)

    browser.close()

if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)
