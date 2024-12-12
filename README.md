# World Bank Staff Profile Scraper

The project generates two main datasets with comprehensive information about World Bank staff:
- src/wb_scraping/output/persons_profiles_with_collaborators.csv
- src/wb_scraping/output/linkedin_processed.csv

This project is a web scraping tool designed to extract profile information for World Bank staff members from the internal World Bank intranet and from LinkedIn. It automates the process of collecting detailed information about employees, including their work history, education, skills, and project involvement.

## Overview

- Scrapes individual staff profiles from the World Bank intranet
- Extracts comprehensive data including:
  - Basic information (name, unit, location, etc.)
  - Work experience within the World Bank
  - Pre-Bank work experience
  - Formal education
  - Documents and reports authored
  - Areas of expertise and skills
  - Language proficiency
  - Awards received
  - Project involvement (lending, non-lending, and IFC projects)
- Handles pagination for projects
- Saves profile images
- Outputs data in both CSV and JSON formats

## Notes

- The script requires access to the World Bank intranet and appropriate login credentials
- It uses Playwright for browser automation and handles "See All" buttons to ensure comprehensive data collection
- The scraper includes logic to avoid duplicate scraping of profiles
- Error handling is implemented to manage various scenarios during the scraping process

## Setup and Usage

1. Ensure you have Python 3.11 installed
2. Install PDM if you haven't already: `pip install pdm`
3. Clone the repository and navigate to the project directory
4. Install the project dependencies using PDM: `pdm install`
5. Install Playwright browsers: `pdm run playwright install`
6. Place the input CSV file `FCI staff as of 7.31.2024.csv` with staff names in the `src/wb_scraping/data` directory
7. Run the main script: `pdm run python src/wb_scraping/main.py`
8. Run the LinkedIn script: `pdm run python src/wb_scraping/linkedin_scraper.py`. If credentials are not set, this will error out. More details: https://pypi.org/project/proxycurl-py/
9. Run `person_processing.ipynb` and run it. This adds:
 - The top collaborators of each person 
 - Converts columns that are python output to JSON so they are easier to parse from R or other programming lanaguages.
 - Cleans up `src/wb_scraping/output/linkedin_results.csv` and convers it to `linkedin_processed.csv`


## Input

The script expects a CSV file named "FCI staff list as of Dec 31 2023.csv" in the `src/wb_scraping/data` directory. This file should contain a list of staff names to be scraped.

## Output

The script generates several output files in the `src/wb_scraping/output` directory:

### Profile scraping
- `person_profiles_with_collaborators.csv`. Final output of profile scraping.

Intermediary outputs:
- `persons_profiles.csv`: Output file with all scraped profile data before being processed by `person_processing.ipynb`
- `persons_profiles.json`: JSON version of the profile data
- `persons_not_found.csv`: List of staff names that couldn't be found
- `photos/`: Directory containing saved profile images

### LinkedIn Scraping
- `linkedin_processed.csv`: Main output of linkedin scraping

Intermediary ouputs:
- linkedin_results.csv: Outputfile after scraping, before being processed by `person_processing.ipynb`

## Dependencies

For a complete list of dependencies, refer to the `pyproject.toml` file.


## Disclaimer

This tool is for internal use only and should be used in compliance with World Bank policies and data protection regulations.