from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("browser_profile").resolve()

def main():
    PROFILE_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
            slow_mo=150,
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=60000)
        print("\nLog into Facebook in the browser window.")
        print("When you can see your normal Facebook home/page, come back here and press ENTER.")
        input()
        context.close()

if __name__ == "__main__":
    main()
