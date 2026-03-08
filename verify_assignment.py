from playwright.sync_api import sync_playwright

def test_assignment():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # We assume server is running on localhost:8000
        page.goto("http://localhost:8000/auth/login/")
        page.fill("input[name='username']", "test_admin")
        page.fill("input[name='password']", "adminpass")
        page.click("button[type='submit']")

        # Navigate to the assignment match page with step=3 directly
        page.goto("http://localhost:8000/canteen/hr/assignment_match/?step=3")

        # Check if the checkboxes have IDs and labels are working by clicking the label
        # Get the first label in the form-check group and click it
        label = page.locator("label.form-check-label").first
        print(f"Clicking label for: {label.inner_text()}")

        # Assert that checking it via label click toggles the state
        checkbox = page.locator("input[type='checkbox']").first
        was_checked = checkbox.is_checked()

        label.click()
        is_checked = checkbox.is_checked()
        print(f"State changed from {was_checked} to {is_checked}")
        assert was_checked != is_checked, "Label click did not toggle checkbox state!"

        # Create a screenshot
        import os
        os.makedirs("/home/jules/verification", exist_ok=True)
        page.screenshot(path="/home/jules/verification/assignment_match.png", full_page=True)

        # Try adding a new block
        page.click("button:has-text('إضافة مادة أخرى')")
        page.screenshot(path="/home/jules/verification/assignment_match_added_block.png", full_page=True)

        browser.close()

test_assignment()
