from playwright.sync_api import sync_playwright, expect
import os

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    try:
        # Navigate to settings page with correct prefix
        url = "http://localhost:8000/canteen/settings/"
        response = page.goto(url)
        print(f"Loaded page {url} with status: {response.status}")

        # Check for login modal visibility
        # The modal might appear after a short delay or due to JS
        # Let's wait a bit
        page.wait_for_timeout(2000)

        if page.locator("#loginModal").is_visible():
            print("Login Modal appeared. Attempting login...")
            page.fill("#username", "test_user")
            page.fill("#password", "testpass")
            # The button inside the form
            page.click("#loginForm button[type=submit]")
            # Wait for modal to disappear
            page.wait_for_selector("#loginModal", state="hidden", timeout=5000)
            print("Login successful.")
        else:
            print("Login Modal not visible. Assuming access granted.")

        # Verify the checkbox
        print("Checking for 'Update Existing' checkbox...")
        checkbox = page.locator("#updateExisting")
        expect(checkbox).to_be_visible()
        print("Checkbox is visible!")

        # Verify Label
        label = page.locator("label[for='updateExisting']")
        expect(label).to_contain_text("تحديث البيانات الموجودة")
        print("Label is correct!")

        # Take screenshot
        if not os.path.exists("verification"):
            os.makedirs("verification")
        screenshot_path = "verification/verification.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

    except Exception as e:
        print(f"Error: {e}")
        if not os.path.exists("verification"):
            os.makedirs("verification")
        page.screenshot(path="verification/error.png")
    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
