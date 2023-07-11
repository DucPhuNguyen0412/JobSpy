from typing import Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from fastapi import status

from api.core.scrapers import Scraper, ScraperInput, Site
from api.core.jobs import *


class LinkedInScraper(Scraper):
    def __init__(self):
        """
        Initializes LinkedInScraper with the LinkedIn job search url
        """
        site = Site(Site.LINKEDIN)
        super().__init__(site)

        self.url = "https://www.linkedin.com/jobs"

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        """
        Scrapes LinkedIn for jobs with scraper_input criteria
        :param scraper_input:
        :return: job_response
        """
        job_list: list[JobPost] = []
        seen_urls = set()
        page, processed_jobs, job_count = 0, 0, 0

        with requests.Session() as session:
            while len(job_list) < scraper_input.results_wanted:
                params = {
                    "pageNum": page,
                    "location": scraper_input.location,
                    "distance": scraper_input.distance,
                }

                self.url = f"{self.url}/{scraper_input.search_term}-jobs"
                response = session.get(self.url, params=params, allow_redirects=True)

                if response.status_code != status.HTTP_200_OK:
                    return JobResponse(
                        success=False,
                        error=f"Response returned {response.status_code}",
                    )

                soup = BeautifulSoup(response.text, "html.parser")

                if page == 0:
                    job_count_text = soup.find(
                        "span", class_="results-context-header__job-count"
                    ).text
                    job_count = int("".join(filter(str.isdigit, job_count_text)))

                for job_card in soup.find_all(
                    "div",
                    class_="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card",
                ):
                    job_url_tag = job_card.find("a", class_="base-card__full-link")
                    job_url = job_url_tag["href"] if job_url_tag else "N/A"
                    if job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)
                    job_info = job_card.find("div", class_="base-search-card__info")
                    if job_info is None:
                        continue
                    title_tag = job_info.find("h3", class_="base-search-card__title")
                    title = title_tag.text.strip() if title_tag else "N/A"

                    company_tag = job_info.find("a", class_="hidden-nested-link")
                    company = company_tag.text.strip() if company_tag else "N/A"

                    metadata_card = job_info.find(
                        "div", class_="base-search-card__metadata"
                    )
                    location: Location = LinkedInScraper.get_location(metadata_card)

                    datetime_tag = metadata_card.find(
                        "time", class_="job-search-card__listdate"
                    )
                    if datetime_tag:
                        datetime_str = datetime_tag["datetime"]
                        date_posted = datetime.strptime(datetime_str, "%Y-%m-%d")
                    else:
                        date_posted = None

                    job_post = JobPost(
                        title=title,
                        company_name=company,
                        location=location,
                        date_posted=date_posted,
                        delivery=Delivery(method=DeliveryEnum.URL, value=job_url),
                    )
                    job_list.append(job_post)
                    if len(job_list) >= scraper_input.results_wanted:
                        break
                if (
                    len(job_list) >= scraper_input.results_wanted
                    or processed_jobs >= job_count
                ):
                    break

                page += 1

        job_list = job_list[: scraper_input.results_wanted]
        job_response = JobResponse(
            success=True,
            jobs=job_list,
            job_count=job_count,
        )
        return job_response

    @staticmethod
    def get_location(metadata_card: Optional[Tag]) -> Location:
        """
        Extracts the location data from the job metadata card.
        :param metadata_card
        :return: location
        """
        location = Location(
            country="US",
        )
        if metadata_card is not None:
            location_tag = metadata_card.find(
                "span", class_="job-search-card__location"
            )
            location_string = location_tag.text.strip() if location_tag else "N/A"
            parts = location_string.split(", ")
            if len(parts) == 2:
                city, state = parts
                location = Location(
                    country="US",
                    city=city,
                    state=state,
                )

        return location