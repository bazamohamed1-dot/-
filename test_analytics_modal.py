from playwright.sync_api import sync_playwright
import time

def test_modal(page):
    page.goto("http://localhost:8000/canteen/")
    page.fill('input#username', 'admin')
    page.fill('input#password', 'admin')
    page.click('button[type="submit"]')
    page.wait_for_url("**/canteen/dashboard/**")

    page.goto("http://localhost:8000/canteen/analytics/")
    page.wait_for_load_state("networkidle")

    # Click to open modal
    page.evaluate("openAnalyticsTeacherAssignmentsModal()")

    # Wait for modal to be visible
    page.wait_for_selector("#analyticsTeacherAssignmentsModal", state="visible")

    # Select the first teacher
    page.select_option("#teacherSelect", index=1)

    # Wait for the assignment block to render
    page.wait_for_selector(".analytics-assignment-block")

    # Take screenshot
    time.sleep(1) # wait for animation
    page.screenshot(path="/home/jules/verification3.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_modal(page)
        finally:
            browser.close()
