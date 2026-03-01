"""
Scraper Adzuna — API gratuite d'offres d'emploi.
Inscription: https://developer.adzuna.com/
"""

import os
import requests
from datetime import datetime
from .base import BaseScraper, JobOffer


class AdzunaScraper(BaseScraper):
    """Scraper utilisant l'API gratuite Adzuna."""
    
    def __init__(self, config: dict, profile: dict):
        super().__init__(config, profile)
        self.source_name = "adzuna"
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")
        self.base_url = config.get("apis", {}).get("adzuna", {}).get(
            "base_url", "https://api.adzuna.com/v1/api/jobs"
        )
        # Only CH - FR returns 0 results for Swiss border jobs
        self.countries = ["ch"]
        self.results_per_page = config.get("apis", {}).get("adzuna", {}).get(
            "results_per_page", 50
        )
    
    def search(self, query: str, location: str, **kwargs) -> list[JobOffer]:
        """Recherche via l'API Adzuna."""
        offers = []
        
        for country in self.countries:
            try:
                results = self._api_search(query, location, country)
                offers.extend(results)
            except Exception as e:
                print(f"    ⚠️  Adzuna [{country}] erreur: {e}")
        
        return offers
    
    def _api_search(self, query: str, location: str, country: str) -> list[JobOffer]:
        """Appel API Adzuna pour un pays donné."""
        url = f"{self.base_url}/{country}/search/1"
        
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.results_per_page,
            "what": query,
            "where": location,
            "content-type": "application/json",
            "sort_by": "date",
            "max_days_old": 14,  # Offres de moins de 14 jours seulement
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        offers = []
        for result in data.get("results", []):
            offer = JobOffer(
                title=result.get("title", "").strip(),
                company=result.get("company", {}).get("display_name", "Unknown"),
                location=result.get("location", {}).get("display_name", ""),
                description=result.get("description", ""),
                url=result.get("redirect_url", ""),
                salary=self._format_salary(result),
                contract_type=result.get("contract_type", None),
                posted_date=result.get("created", ""),
                source="adzuna",
            )
            offers.append(offer)
        
        print(f"    ✅ Adzuna [{country}]: {len(offers)} offres pour '{query}'")
        return offers
    
    def _format_salary(self, result: dict) -> str | None:
        """Formate le salaire depuis les données Adzuna."""
        salary_min = result.get("salary_min")
        salary_max = result.get("salary_max")
        
        if salary_min and salary_max:
            return f"{int(salary_min):,} - {int(salary_max):,}"
        elif salary_min:
            return f"À partir de {int(salary_min):,}"
        elif salary_max:
            return f"Jusqu'à {int(salary_max):,}"
        return None


class SwissDevJobsScraper(BaseScraper):
    """
    Scraper pour SwissDevJobs.ch — Site spécialisé tech en Suisse.
    URL format: /jobs/{category}/{location}
    Categories: Data, AI, DevOps, Cloud, all
    Locations: Geneva, Lausanne, all
    """
    
    def __init__(self, config: dict, profile: dict):
        super().__init__(config, profile)
        self.source_name = "swissdevjobs"
        self.base_url = "https://swissdevjobs.ch"
    
    def search_all(self) -> list[JobOffer]:
        """Recherche avec les bonnes combinaisons catégorie/location."""
        from bs4 import BeautifulSoup
        
        all_offers = []
        seen_ids = set()
        
        # Combinaisons catégorie + location — Genève et Vaud uniquement
        searches = [
            ("Data", "Geneva"),
            ("Data", "Lausanne"),
            ("AI", "Geneva"),
            ("AI", "Lausanne"),
            ("DevOps", "Geneva"),
            ("DevOps", "Lausanne"),
            ("Cloud", "Geneva"),
            ("Cloud", "Lausanne"),
            ("all", "Geneva"),
            ("all", "Lausanne"),
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        }
        
        for category, location in searches:
            try:
                url = f"{self.base_url}/jobs/{category}/{location}"
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Chercher les liens d'offres (format: /jobs/Company-Job-Title)
                job_links = soup.select("a[href*='/jobs/'][href*='-']")
                
                for link in job_links[:15]:
                    href = link.get("href", "")
                    text = link.get_text(strip=True)
                    
                    # Filtrer les liens de navigation
                    if not text or len(text) < 5 or href.count("/") > 3:
                        continue
                    if any(skip in href.lower() for skip in ["/salaries/", "/communities/", "/blog/"]):
                        continue
                    
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    
                    # Extraire le salaire s'il est visible
                    parent = link.find_parent()
                    salary_text = ""
                    if parent:
                        salary_el = parent.find(string=lambda s: s and "CHF" in s if s else False)
                        if salary_el:
                            salary_text = salary_el.strip()
                    
                    offer = JobOffer(
                        title=text,
                        company="",  # Sera dans le titre ou la page détaillée
                        location=location if location != "all" else "Switzerland",
                        description=f"Category: {category}",
                        url=full_url,
                        salary=salary_text or None,
                        source="swissdevjobs",
                    )
                    
                    if offer.id not in seen_ids:
                        seen_ids.add(offer.id)
                        all_offers.append(offer)
                
                count = len([o for o in all_offers if o.id in seen_ids])
                
            except Exception as e:
                print(f"    ⚠️  SwissDevJobs [{category}/{location}] erreur: {e}")
        
        print(f"    ✅ SwissDevJobs: {len(all_offers)} offres au total")
        return all_offers
    
    def search(self, query: str, location: str, **kwargs) -> list[JobOffer]:
        """Non utilisé — search_all est surchargé."""
        return []


class AdzunaBroadScraper(BaseScraper):
    """
    Scraper Adzuna élargi — recherche avec des termes génériques
    sur TOUTE la Suisse (pas de filtre location) pour capter plus d'offres.
    """
    
    def __init__(self, config: dict, profile: dict):
        super().__init__(config, profile)
        self.source_name = "adzuna_broad"
        self.app_id = os.getenv("ADZUNA_APP_ID", "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")
        self.base_url = config.get("apis", {}).get("adzuna", {}).get(
            "base_url", "https://api.adzuna.com/v1/api/jobs"
        )
    
    def search_all(self) -> list[JobOffer]:
        """Recherche élargie — termes génériques, pas de filtre location."""
        all_offers = []
        seen_ids = set()
        
        # Requêtes larges par catégorie — focalisées Genève/Lausanne/Vaud
        broad_queries = [
            ("python data engineer", "Geneva"),
            ("python data engineer", "Lausanne"),
            ("machine learning", "Geneva"),
            ("machine learning", "Lausanne"),
            ("artificial intelligence", "Geneva"),
            ("power bi analyst", "Geneva"),
            ("power bi analyst", "Lausanne"),
            ("databricks engineer", "Geneva"),
            ("data pipeline ETL", "Geneva"),
            ("data pipeline ETL", "Lausanne"),
            ("LLM generative AI", "Geneva"),
            ("data scientist", "Geneva"),
            ("data scientist", "Lausanne"),
            ("business intelligence", "Lausanne"),
        ]
        
        for query, location in broad_queries:
            try:
                url = f"{self.base_url}/ch/search/1"
                params = {
                    "app_id": self.app_id,
                    "app_key": self.app_key,
                    "results_per_page": 25,
                    "what": query,
                    "content-type": "application/json",
                    "sort_by": "date",
                    "max_days_old": 14,  # Offres de moins de 14 jours seulement
                }
                # Ajouter la location seulement si spécifiée
                if location:
                    params["where"] = location
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                count = 0
                for result in data.get("results", []):
                    offer = JobOffer(
                        title=result.get("title", "").strip(),
                        company=result.get("company", {}).get("display_name", "Unknown"),
                        location=result.get("location", {}).get("display_name", ""),
                        description=result.get("description", ""),
                        url=result.get("redirect_url", ""),
                        salary=self._format_salary(result),
                        contract_type=result.get("contract_type", None),
                        posted_date=result.get("created", ""),
                        source="adzuna_broad",
                    )
                    if offer.id not in seen_ids:
                        seen_ids.add(offer.id)
                        all_offers.append(offer)
                        count += 1
                
                if count > 0:
                    print(f"    ✅ Adzuna [broad]: {count} offres pour '{query}'"
                          f"{f' @ {location}' if location else ''}")
                
            except Exception as e:
                print(f"    ⚠️  Adzuna [broad] erreur pour '{query}': {e}")
        
        print(f"    📊 Adzuna Broad total: {len(all_offers)} offres uniques")
        return all_offers
    
    def search(self, query: str, location: str, **kwargs) -> list[JobOffer]:
        """Non utilisé — search_all est surchargé."""
        return []
    
    def _format_salary(self, result: dict) -> str | None:
        """Formate le salaire."""
        salary_min = result.get("salary_min")
        salary_max = result.get("salary_max")
        if salary_min and salary_max:
            return f"{int(salary_min):,} - {int(salary_max):,}"
        elif salary_min:
            return f"À partir de {int(salary_min):,}"
        elif salary_max:
            return f"Jusqu'à {int(salary_max):,}"
        return None
