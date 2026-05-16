import asyncio
from playwright.async_api import async_playwright


async def login():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context()

        page = await context.new_page()

        await page.goto("https://divar.ir")

        print("Login manually then press ENTER...")

        input()

        await context.storage_state(path="divar_state.json")

        print("Login session saved.")

        await browser.close()


asyncio.run(login())
