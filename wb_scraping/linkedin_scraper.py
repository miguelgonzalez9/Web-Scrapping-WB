import sys
import csv
from pathlib import Path
from proxycurl.asyncio import Proxycurl
import asyncio
import os
import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict

csv.field_size_limit(sys.maxsize)

@dataclass
class LinkedInProfile:
    full_name: str
    linkedin_url: str = ""
    public_identifier: str = ""
    profile_pic_url: str = ""
    background_cover_image_url: str = ""
    first_name: str = ""
    last_name: str = ""
    occupation: str = ""
    headline: str = ""
    summary: str = ""
    country: str = ""
    country_full_name: str = ""
    city: str = ""
    state: str = ""
    experiences: List[Dict] = field(default_factory=list)
    education: List[Dict] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    accomplishment_projects: List[Dict] = field(default_factory=list)
    certifications: List[Dict] = field(default_factory=list)
    connections: int = 0
    recommendations: List[str] = field(default_factory=list)
    activities: List[Dict] = field(default_factory=list)
    similarly_named_profiles: List[Dict] = field(default_factory=list)
    education_titles: List[str] = field(default_factory=list)
    non_world_bank_experiences: List[Dict] = field(default_factory=list)
    raw_data: Optional[dict] = None

async def lookup_person_from_csv(csv_file_path, output_dir):
    """Reads a CSV file containing full names, performs LinkedIn profile lookup for each person, and saves results incrementally."""
    csv_file = Path(csv_file_path)
    if not csv_file.exists():
        print(f"File {csv_file_path} does not exist.")
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv_path = output_dir / 'linkedin_results.csv'

    api = Proxycurl()
    results = load_existing_results(output_csv_path)
    results_dict = {profile.full_name: profile for profile in results}

    with csv_file.open(mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            full_name = row['Name (Full)']
            last_name, first_name = full_name.split(',')
            last_name, first_name = last_name.strip(), first_name.strip()
            company_domain = "worldbank.org"

            if full_name in results_dict:
                print(f"Skipping {full_name} - already processed")
                continue

            name_variations = list(set([
                (first_name, last_name),
                (first_name.split()[0], last_name),
                (first_name, last_name.split()[0]),
                (first_name.split()[0], last_name.split()[0]),
            ]))

            profile = None
            for first, last in name_variations:
                profile = await process_person(api, first, last, company_domain, full_name)
                if profile and profile.linkedin_url:
                    print(f"Found results for {first} {last}")
                    results.append(profile)
                    results_dict[full_name] = profile
                    break

            if not profile or not profile.linkedin_url:
                print(f"No results found for any variation of {full_name}")
                profile = LinkedInProfile(full_name=full_name)
                results.append(profile)
                results_dict[full_name] = profile

            save_to_csv(results, output_csv_path)

async def process_person(api, first_name, last_name, company_domain, full_name):
    lookup_results = await api.linkedin.person.resolve(first_name=first_name, last_name=last_name, company_domain=company_domain, similarity_checks="skip", enrich_profile="enrich")
    if lookup_results is None or (lookup_results['url'] is None and lookup_results['name_similarity_score'] is None):
        print(f"No results found for {first_name} {last_name}")
        return None

    profile = lookup_results.get('profile', {})
    experiences = profile.get('experiences', [])
    education = profile.get('education', [])

    non_world_bank_experiences = [
        exp for exp in experiences
        if exp and exp.get('company') is not None and "world bank" not in exp.get('company', '').lower()
    ]

    education_titles = [
        edu.get('degree_name', 'Unknown')
        for edu in education
        if edu and edu.get('degree_name')
    ]

    return LinkedInProfile(
        full_name=full_name,
        linkedin_url=lookup_results.get('url', ''),
        public_identifier=profile.get('public_identifier', ''),
        profile_pic_url=profile.get('profile_pic_url', ''),
        background_cover_image_url=profile.get('background_cover_image_url', ''),
        first_name=profile.get('first_name', ''),
        last_name=profile.get('last_name', ''),
        occupation=profile.get('occupation', ''),
        headline=profile.get('headline', ''),
        summary=profile.get('summary', ''),
        country=profile.get('country', ''),
        country_full_name=profile.get('country_full_name', ''),
        city=profile.get('city', ''),
        state=profile.get('state', ''),
        experiences=experiences,
        education=education,
        languages=profile.get('languages', []),
        accomplishment_projects=profile.get('accomplishment_projects', []),
        certifications=profile.get('certifications', []),
        connections=profile.get('connections', 0),
        recommendations=profile.get('recommendations', []),
        activities=profile.get('activities', []),
        similarly_named_profiles=profile.get('similarly_named_profiles', []),
        education_titles=education_titles,
        non_world_bank_experiences=non_world_bank_experiences,
        raw_data=lookup_results
    )

def load_existing_results(output_csv_path):
    results = []
    if os.path.exists(output_csv_path):
        with open(output_csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                for field in ['experiences', 'education', 'accomplishment_projects', 'certifications', 'activities', 'similarly_named_profiles', 'recommendations', 'raw_data', 'non_world_bank_experiences']:
                    if row[field]:
                        row[field] = json.loads(row[field])
                row['languages'] = row['languages'].split(', ') if row['languages'] else []
                row['education_titles'] = row['education_titles'].split(', ') if row['education_titles'] else []
                row['connections'] = int(row['connections']) if row['connections'] else 0
                results.append(LinkedInProfile(**row))
    return results

def save_to_csv(results, output_csv_path):
    fieldnames = [
        'full_name', 'linkedin_url', 'public_identifier', 'profile_pic_url',
        'background_cover_image_url', 'first_name', 'last_name', 'occupation',
        'headline', 'summary', 'country', 'country_full_name', 'city', 'state',
        'experiences', 'education', 'languages', 'accomplishment_projects',
        'certifications', 'connections', 'recommendations', 'activities',
        'similarly_named_profiles', 'education_titles', 'non_world_bank_experiences', 'raw_data'
    ]
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for profile in results:
            row = asdict(profile)
            # Convert complex fields to JSON strings
            for field in ['experiences', 'education', 'accomplishment_projects', 'certifications', 'activities', 'similarly_named_profiles', 'recommendations', 'non_world_bank_experiences', 'raw_data']:
                row[field] = json.dumps(row[field])
            row['languages'] = ', '.join(row['languages'])
            row['education_titles'] = ', '.join(row['education_titles'])
            writer.writerow(row)


csv_file_path = 'src/wb_scraping/data/FCI staff as of 7.31.2024.csv'
output_dir = 'src/wb_scraping/output'
asyncio.run(lookup_person_from_csv(csv_file_path, output_dir))