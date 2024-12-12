import asyncio

from config import DATA_PATH, OUTPUT_PATH
from data_processing import (
    read_existing_profiles,
    read_staff_names,
    save_names_not_found,
    save_profile_data,
    save_profile_data_json,
)
from playwright.async_api import async_playwright, TimeoutError
from scraper import PersonProfileScraper


async def main():
    staff_names = read_staff_names(DATA_PATH / "FCI staff as of 7.31.2024.csv")
    existing_profiles = read_existing_profiles(OUTPUT_PATH / "persons_profiles.csv")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="state.json")
        page = await context.new_page()

        for name in staff_names:
            scraper = PersonProfileScraper(page=page, name=name)

            if name in existing_profiles:
                print(f"Skipping {name} as it's already in the profiles.")
                continue

            await page.goto("https://intranet.worldbank.org/people/search")
            await context.storage_state(path="state.json")

            await page.fill("input[id='sf_sample__text_id']", name)
            await page.keyboard.press("Enter")

            first_result = page.locator(".sf-people-name").first

            try:
                await first_result.wait_for()
            except TimeoutError:
                save_names_not_found(name)
                continue

            if first_result:
                first_result_text = await first_result.inner_text()
                if name not in first_result_text:
                    save_names_not_found(name)
                    continue
                await first_result.click()
                profile_data = await scraper.scrape_profile()
                save_profile_data(profile_data)
                save_profile_data_json(profile_data)
            else:
                save_names_not_found(name)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
