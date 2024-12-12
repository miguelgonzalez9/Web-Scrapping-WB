import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from config import OUTPUT_PATH
from playwright.async_api import ElementHandle, Page, expect


@dataclass
class ProfileData:
    name: str
    official_unit_name: str
    current_unit_name: str
    unit_code: str
    work_and_duty_location: str
    room_number: str
    url: str
    upi: str
    years_in_current_position: float
    years_in_fci: float
    years_in_bank: float
    last_position: str
    all_positions: str
    pre_bank_experience: List[dict]
    formal_education: Optional[List[dict]]
    documents_and_reports: List[dict]
    document_ids: List[str]
    areas_of_expertise: List[str]
    skills: List[str]
    languages: List[dict]
    list_of_awards: str
    total_number_of_awards: int
    lending_projects: List[str]
    lending_project_codes: List[str]
    lending_project_statuses: List[str]
    lending_project_years: List[str]
    non_lending_projects: List[str]
    non_lending_project_codes: List[str]
    non_lending_project_statuses: List[str]
    non_lending_project_years: List[str]
    ifc_projects: List[str]
    ifc_project_codes: List[str]
    ifc_project_statuses: List[str]
    ifc_project_years: List[str]
    all_projects: List[str]
    all_project_codes: List[str]
    all_project_statuses: List[str]
    all_project_years: List[str]

    def __setattr__(self, name: str, value: Any) -> None:
        if name not in self.__annotations__:
            raise AttributeError(f"{self.__class__.__name__} does not have attribute '{name}'")
        super().__setattr__(name, value)

    def update(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass
class ProjectTypeData:
    projects: List[str]
    project_codes: List[str]
    project_statuses: List[str]
    project_years: List[str]


@dataclass
class ProjectData:
    lending: ProjectTypeData
    non_lending: ProjectTypeData
    ifc: ProjectTypeData

    @property
    def all_projects(self):
        return self.lending.projects + self.non_lending.projects + self.ifc.projects

    @property
    def all_project_codes(self):
        return self.lending.project_codes + self.non_lending.project_codes + self.ifc.project_codes

    @property
    def all_project_statuses(self):
        return self.lending.project_statuses + self.non_lending.project_statuses + self.ifc.project_statuses

    @property
    def all_project_years(self):
        return self.lending.project_years + self.non_lending.project_years + self.ifc.project_years


class PersonProfileScraper:
    def __init__(self, page: Page, name: str):
        self.page = page
        self.name = name

    async def scrape_profile(self) -> ProfileData:
        await self._wait_for_profile_load()

        see_all_buttons = await self.page.query_selector_all("a:has-text('See All')")
        for button in see_all_buttons:
            if button and await button.is_visible():
                await button.click()

        profile_dict = await self._extract_basic_info(self.name)

        profile_dict.update(await self._extract_bank_experience())
        profile_dict.update(await self._extract_pre_bank_experience())
        profile_dict.update(await self._extract_formal_education())
        profile_dict.update(await self._extract_documents_and_reports())
        profile_dict.update(await self._extract_expertise_and_skills())
        profile_dict.update(await self._extract_awards())

        await self._download_profile_image(upi=profile_dict['upi'])

        project_data = await PersonProjectsScraper(self.page, name=self.name).scrape_projects()
        profile_dict.update(project_data)

        # This will raise a TypeError if any required attribute is missing
        return ProfileData(**profile_dict)

    async def _wait_for_profile_load(self):
        await asyncio.gather(
            expect(self.page.locator(".sf-profile-name").first).to_contain_text(self.name, timeout=5000),
            expect(self.page.locator("text='Profile Completion'")).to_be_visible(timeout=5000),
            expect(self.page.locator(selector="text='Profile Views'")).to_be_visible(timeout=5000),
            #expect(self.page.locator("text=/View (All )?Projects?/i")).to_be_visible(timeout=5000),
        )

    async def _click_see_all_and_wait_for_content(self, button_selector: str, content_selector: str):
        see_all_button = self.page.locator(button_selector)
        if await see_all_button.count() > 0:
            button_text = await see_all_button.inner_text()
            if "See All" in button_text:
                await see_all_button.click()
                # Wait for the button text to change to "See Less"
                await expect(see_all_button).to_have_text(expected="See Less", timeout=5000)

    async def _extract_basic_info(self, name: str) -> dict:
        return {
            "name": name,
            "official_unit_name": await self._get_text_content("a[data-customlink='nl:officialunit'] span"),
            "current_unit_name": await self._get_text_content("a[data-customlink='nl:currentunit'] span"),
            "unit_code": await self._get_unit_code(),
            "work_and_duty_location": await self._get_text_content(
                "//div[contains(text(), 'Work Location')]/following-sibling::div[not(@class='sf-time-zone')]"
            ),
            "room_number": await self._get_room_and_mail_stop(),
            "url": self.page.url,
            "upi": self.page.url.split("/")[-1][-6:],
        }

    async def _get_unit_code(self) -> str:
        unit_code_element = await self.page.query_selector("p.sf-profile-unit a[data-customlink='nl:unit']")
        if unit_code_element:
            unit_code = await unit_code_element.inner_text()
            return unit_code.strip()
        return "N/A"

    async def _extract_bank_experience(self) -> dict:
        bank_experience = await self.page.query_selector_all(".sf-bank-exp-new-loop .sf-experience-details")
        current_position_start = None
        bank_start = None
        last_position = ""
        all_positions = []
        years_in_fci = 0.0
        next_position_start_date = datetime.now()

        for exp in bank_experience:
            date_elem = await exp.query_selector(".sf-experience-from")
            if date_elem:
                date_str = await date_elem.inner_text()
                date_str = date_str.strip()
                date = datetime.strptime(date_str, "%b %d, %Y")
            else:
                continue

            designation_elem = await exp.query_selector(".sf-designation")
            designation = await designation_elem.inner_text() if designation_elem else ""

            unit_elem = await exp.query_selector(".sf-units")
            unit = await unit_elem.inner_text() if unit_elem else ""

            if not bank_start or bank_start > date:
                bank_start = date

            if "FCI" in unit or "Finance, Competitiveness & Innovation" in unit:
                years_in_fci += await self._calculate_years(start_date=date, end_date=next_position_start_date)

            if not current_position_start:
                current_position_start = date
                last_position = f"{designation} - {unit}"

            all_positions.append(f"{date_str}: {designation} - {unit}")
            next_position_start_date = date

        years_in_current_position = await self._calculate_years(current_position_start) if current_position_start else 0
        years_in_bank = await self._calculate_years(bank_start) if bank_start else 0

        return {
            "years_in_current_position": years_in_current_position,
            "years_in_fci": years_in_fci,
            "years_in_bank": years_in_bank,
            "last_position": last_position,
            "all_positions": "; ".join(all_positions),
        }

    async def _extract_pre_bank_experience(self) -> dict[str, list[dict[str, str]]]:
        # Click on the "Pre-Bank Experience" tab
        pre_bank_tab = self.page.locator("span[data-customlink='tb:prebankexperience']")
        if await pre_bank_tab.count() == 0:
            print(f"Pre-Bank Experience tab not found for {self.name}")
            return {"pre_bank_experience": [{}]}

        await pre_bank_tab.click()

        # Since this "See All" was not initially available in the page, we need to click it
        await self._click_see_all_and_wait_for_content(
            "a[data-customlink='nl:prebankviewall']", "app-pre-bank-experience ul.sf-vertical-list li.sf-details"
        )

        experience_items = await self.page.query_selector_all(
            "app-pre-bank-experience ul.sf-vertical-list li.sf-details"
        )

        pre_bank_experiences: list[dict[str, str]] = []
        for item in experience_items:
            title = await item.query_selector(".sf-title-txt")
            organization = await item.query_selector("div:not(.sf-title-txt):not(.sf-content-txt)")
            date_range = await item.query_selector(".sf-content-txt.mt-1")

            if title and organization and date_range:
                pre_bank_experiences.append(
                    {
                        "title": await title.inner_text(),
                        "organization": await organization.inner_text(),
                        "date_range": await date_range.inner_text(),
                    }
                )

        return {"pre_bank_experience": pre_bank_experiences}

    async def _extract_formal_education(self) -> dict[str, list[dict[str, str]] | None]:
        # Click on the "Formal Education" tab
        education_tab = self.page.locator("span[data-customlink='tb:formaleducation']")
        if await education_tab.count() == 0:
            print(f"Formal Education tab not found for {self.name}")
            return {"formal_education": None}

        await education_tab.click()
        await self.page.wait_for_load_state("networkidle")

        # Since this "See All" might not be initially available in the page, we need to click it
        await self._click_see_all_and_wait_for_content(
            "a[data-customlink='nl:formaleducationviewall']", "app-formal-education ul.sf-vertical-list li.sf-details"
        )

        education_items = await self.page.query_selector_all("app-formal-education ul.sf-vertical-list li.sf-details")

        formal_education: list[dict[str, str]] = []
        for item in education_items:
            degree = await item.query_selector(".sf-title-txt")
            institution = await item.query_selector(".sf-content-txt.sf-text-dark")
            year = await item.query_selector(".sf-content-txt.mt-1")

            if degree and institution and year:
                formal_education.append(
                    {
                        "degree": await degree.inner_text(),
                        "institution": await institution.inner_text(),
                        "year": await year.inner_text(),
                    }
                )

        return {"formal_education": formal_education}

    async def _extract_documents_and_reports(self) -> dict:
        documents: list[dict[str, str]] = []
        doc_tab = await self.page.query_selector("span[data-customlink='tb:documentreports']")
        if doc_tab:
            await doc_tab.click()
            try:
                await self.page.wait_for_selector("app-documents-reports", timeout=5000)
                await self._click_see_all_and_wait_for_content(
                    "a[data-customlink='nl:documentsviewall']",
                    "app-documents-reports ul.sf-vertical-list.sf-purple-bullet li.sf-details",
                )
            except Exception as e:
                print(f"No documents and reports found for {self.name}; exception occurred {e}")
                return {"documents_and_reports": [], "document_ids": []}

            doc_entries = await self.page.query_selector_all(
                "app-documents-reports ul.sf-vertical-list.sf-purple-bullet li.sf-details"
            )

            for entry in doc_entries:
                date = await entry.query_selector(".sf-date")
                title = await entry.query_selector(".sf-title-txt a")
                description = await entry.query_selector(".sf-doc-des")

                date_text = await date.inner_text() if date else "N/A"
                title_text = await title.inner_text() if title else "N/A"
                title_link = await title.get_attribute("href") if title else "N/A"
                description_text = await description.inner_text() if description else "N/A"

                doc_id = "N/A"
                if title_link != "N/A":
                    doc_id = title_link.split("/")[-1]

                documents.append(
                    {
                        "id": doc_id,
                        "date": date_text.strip(),
                        "title": title_text.strip(),
                        "link": title_link,
                        "description": description_text.strip(),
                    }
                )

        return {
            "documents_and_reports": documents,
            "document_ids": [doc["id"] for doc in documents],
        }

    async def _extract_expertise_and_skills(self) -> dict:
        return {
            "areas_of_expertise": await self._scrape_areas_of_expertise(),
            "skills": await self._scrape_skills(),
            "languages": await self._scrape_languages(),
        }

    async def _download_profile_image(self, upi: str):
        img_element = await self.page.query_selector(".sf-profile-img img")
        if img_element:
            photo_dir = OUTPUT_PATH / "photos"
            photo_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{upi}.png"
            filepath = photo_dir / filename
            await img_element.screenshot(path=str(filepath))
            print(f"Saved image for UPI: {upi}")
        else:
            print(f"No profile image found for UPI: {upi}")

    async def _get_text_content(self, selector: str, element: ElementHandle | None = None) -> Optional[str]:
        if element is None:
            el = await self.page.query_selector(selector)
        else:
            el = await element.query_selector(selector)

        return await el.inner_text() if el else None

    async def _extract_awards(self) -> dict:
        awards = []
        total_awards = 0

        award_elements = await self.page.query_selector_all("div.sf-awards ul li")
        for award_elem in award_elements:
            award_name = await self._get_text_content(selector=".sf-bold", element=award_elem)
            dept = await self._get_text_content(selector=".sf-dept", element=award_elem)
            date = await self._get_text_content(selector=".sf-date", element=award_elem)

            if award_name and dept and date:
                awards.append(f"{award_name}|{dept}|{date}")
                total_awards += 1

        return {"list_of_awards": ", ".join(awards), "total_number_of_awards": total_awards}

    async def _get_room_and_mail_stop(self) -> str:
        room_container = await self.page.query_selector(".sf-info-set:has(.sf-info-title:has-text('Room No'))")
        if room_container:
            full_text = await room_container.inner_text()
            return full_text.replace("Room No", "").strip()
        return ""

    async def _calculate_years(self, start_date: datetime, end_date: Optional[datetime] = None) -> float:
        if end_date is None:
            end_date = datetime.now()
        delta_days = (end_date - start_date).days
        years = delta_days / 365.25
        return round(years, 2)

    async def _scrape_areas_of_expertise(self) -> List[str]:
        areas = []
        expertise_section = await self.page.query_selector(".sf-areas-expertise-section")
        if expertise_section:
            area_elements = await expertise_section.query_selector_all(".sf-area-title")
            for area in area_elements:
                area_text = await area.inner_text()
                areas.append(area_text.strip())
        return areas

    async def _scrape_skills(self) -> List[str]:
        skills = []
        skills_section = await self.page.query_selector(".sf-skills-section")
        if skills_section:
            skill_elements = await skills_section.query_selector_all(".sf-area-title")
            for skill in skill_elements:
                skill_text = await skill.inner_text()
                skills.append(skill_text.strip())
        return skills

    async def _scrape_languages(self) -> List[dict]:
        languages = []
        languages_section = await self.page.query_selector(".sf-languages")
        if languages_section:
            language_elements = await languages_section.query_selector_all(".sf-language-name")
            for lang in language_elements:
                lang_name = await lang.query_selector(".sf-text-secondary")
                lang_level = await lang.query_selector(".sf-lang-item")
                if lang_name:
                    name = await lang_name.inner_text()
                    level = await lang_level.inner_text() if lang_level else "N/A"
                    languages.append({"language": name.strip(), "level": level.strip()})
        return languages


class PersonProjectsScraper:
    def __init__(self, page: Page, name: str):
        self.page = page
        self.name = name

    async def scrape_projects(self) -> dict[str, Any]:
        try:
            view_all_projects = self.page.locator("text='View All Projects'")
            if await view_all_projects.count() > 0:
                await view_all_projects.click()
                await self.page.wait_for_load_state("networkidle", timeout=5000)

            project_data = ProjectData(
                lending=await self._collect_project_type_data("lending"),
                non_lending=await self._collect_project_type_data("nonlending"),
                ifc=await self._collect_project_type_data("ifc"),
            )

            return {
                "lending_projects": project_data.lending.projects,
                "lending_project_codes": project_data.lending.project_codes,
                "lending_project_statuses": project_data.lending.project_statuses,
                "lending_project_years": project_data.lending.project_years,
                "non_lending_projects": project_data.non_lending.projects,
                "non_lending_project_codes": project_data.non_lending.project_codes,
                "non_lending_project_statuses": project_data.non_lending.project_statuses,
                "non_lending_project_years": project_data.non_lending.project_years,
                "ifc_projects": project_data.ifc.projects,
                "ifc_project_codes": project_data.ifc.project_codes,
                "ifc_project_statuses": project_data.ifc.project_statuses,
                "ifc_project_years": project_data.ifc.project_years,
                "all_projects": project_data.all_projects,
                "all_project_codes": project_data.all_project_codes,
                "all_project_statuses": project_data.all_project_statuses,
                "all_project_years": project_data.all_project_years,
            }
        except Exception as e:
            print(f"Error scraping projects for {self.name}: {e}")
            return {
                "lending_projects": [],
                "lending_project_codes": [],
                "lending_project_statuses": [],
                "lending_project_years": [],
                "non_lending_projects": [],
                "non_lending_project_codes": [],
                "non_lending_project_statuses": [],
                "non_lending_project_years": [],
                "ifc_projects": [],
                "ifc_project_codes": [],
                "ifc_project_statuses": [],
                "ifc_project_years": [],
                "all_projects": [],
                "all_project_codes": [],
                "all_project_statuses": [],
                "all_project_years": [],
            }

    async def _collect_project_type_data(self, project_type: str) -> ProjectTypeData:
        try:
            projects = []
            project_codes = []
            project_statuses = []
            project_years = []

            await expect(self.page.locator("h4.card-title.sf-title-lg")).to_contain_text(
                "Project Experience", timeout=5000
            )

            tab = self.page.locator(selector=f"span[data-customlink='tb:{project_type}projects']")
            await expect(tab).to_be_visible(timeout=2000)
            await tab.click()
            await expect(self.page.locator("accordion-group").first).to_be_visible(timeout=5000)

            select_locator = self.page.locator("select[name='noOfRows']")
            if await select_locator.count() > 0:
                await select_locator.select_option("50")

            await expect(self.page.locator("accordion-group").first).to_be_visible(timeout=5000)

            page_number = 1
            while True:
                # Wait for the current page number to be visible
                await expect(self.page.locator(f"li.current:has-text('{page_number}')")).to_be_visible(timeout=5000)

                accordion = self.page.locator("accordion-group")
                count = await accordion.count()

                for i in range(count):
                    project = accordion.nth(i)
                    title_element = project.locator("a.sf-project-title")
                    title = await title_element.inner_text()
                    href = await title_element.get_attribute("href")

                    code = ""
                    if href != "":
                        parts = href.split("/")
                        for part in reversed(parts):
                            if project_type == "ifc":
                                if part.isdigit() and len(part) >= 5:
                                    code = part
                                    break

                            else:
                                if part.startswith("P") and part[1:].isdigit():
                                    code = part
                                    break

                    status_element = project.locator("li.list-inline-item:has-text('Status:') span.sf-dark")
                    status = await status_element.inner_text() if await status_element.count() > 0 else "N/A"
                    year_element = project.locator("li.list-inline-item:has-text('Fiscal Year:') span.sf-dark")
                    year = await year_element.inner_text() if await year_element.count() > 0 else "N/A"

                    projects.append(title.strip())
                    project_codes.append(code)
                    project_statuses.append(status)
                    project_years.append(year)

                # Check if there's a next page
                next_button = self.page.locator("li.pagination-next:not(.disabled) a")
                if await next_button.count() > 0:
                    await next_button.click()
                    page_number += 1
                else:
                    break  # No more pages, exit the loop

            return ProjectTypeData(projects, project_codes, project_statuses, project_years)
        except Exception as e:
            print(f"Error collecting project type data for {project_type} for {self.name}: {e}")
            return ProjectTypeData([], [], [], [])