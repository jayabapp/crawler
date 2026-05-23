import asyncio
from pathlib import Path
import os
from playwright.async_api import async_playwright

PROFILE_DIR = Path(os.getenv("DIVAR_PROFILE_DIR", Path.cwd() / "divar_browser_profile"))
STATE_PATH = Path(os.getenv("DIVAR_STATE_PATH", Path.cwd() / "divar_state.json"))


async def login():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://divar.ir", wait_until="domcontentloaded")

        print("\nاگر لاگین نیستی، لاگین کن.")
        print("اگر کپچا داری، برو روی یک آگهی، نمایش شماره را بزن، کپچا را دستی حل کن.")
        print("بعد از اینکه مطمئن شدی دیوار درست باز می‌شود، ENTER بزن...\n")

        input()

        await context.storage_state(path=str(STATE_PATH))

        print("Login/profile session saved.")
        print(f"Persistent profile: {PROFILE_DIR}")
        print(f"Storage state: {STATE_PATH}")

        await context.close()


if __name__ == "__main__":
    asyncio.run(login())
