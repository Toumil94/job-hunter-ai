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


class JoobleScraper(BaseScraper):
    """
    Scraper pour Jooble — Agrégateur GRATUIT qui récupère les offres de:
    LinkedIn, JobUp, jobs.ch, Indeed, Glassdoor, et des centaines d'autres sites.
    API gratuite: https://jooble.org/api/about
    """
    
    def __init__(self, config: dict, profile: dict):
        super().__init__(config, profile)
        self.source_name = "jooble"
        self.api_key = os.getenv("JOOBLE_API_KEY", "")
        self.base_url = f"https://jooble.org/api/{self.api_key}"
    
    def search_all(self) -> list[JobOffer]:
        """Recherche sur Jooble avec tous les titres de postes."""
        if not self.api_key:
            print("    ⚠️  Jooble: JOOBLE_API_KEY manquante (gratuit: https://jooble.org/api/about)")
            return []
        
        all_offers = []
        seen_ids = set()
        
        # Requêtes ciblées — locations simplifiées pour Jooble
        searches = [
            # IA & ML — Geneva
            ("AI engineer", "Geneva"),
            ("machine learning", "Geneva"),
            ("artificial intelligence", "Geneva"),
            ("deep learning", "Geneva"),
            ("NLP", "Geneva"),
            ("LLM", "Geneva"),
            ("generative AI", "Geneva"),
            ("chatbot developer", "Geneva"),
            ("computer vision", "Geneva"),
            # IA & ML — Lausanne
            ("AI engineer", "Lausanne"),
            ("machine learning", "Lausanne"),
            ("artificial intelligence", "Lausanne"),
            # Data Engineering
            ("data engineer", "Geneva"),
            ("data engineer", "Lausanne"),
            ("data engineer", "Nyon"),
            ("ETL developer", "Geneva"),
            ("databricks", "Geneva"),
            ("Azure data", "Geneva"),
            ("data pipeline", "Geneva"),
            ("data platform", "Geneva"),
            ("data platform", "Lausanne"),
            # Data Science & Analytics
            ("data scientist", "Geneva"),
            ("data scientist", "Lausanne"),
            ("data analyst", "Geneva"),
            ("data analyst", "Lausanne"),
            ("business intelligence", "Geneva"),
            ("business intelligence", "Lausanne"),
            ("Power BI", "Geneva"),
            ("analytics engineer", "Geneva"),
            ("analytics", "Lausanne"),
            # Python / Cloud / DevOps
            ("python developer", "Geneva"),
            ("python developer", "Lausanne"),
            ("MLOps", "Geneva"),
            ("cloud data", "Geneva"),
            # Consultant / Junior / Stage
            ("data consultant", "Geneva"),
            ("data consultant", "Lausanne"),
            ("junior data", "Geneva"),
            ("junior data", "Lausanne"),
            ("intern data", "Geneva"),
            ("graduate data", "Geneva"),
            ("stage data", "Genève"),
            ("stage IA", "Genève"),
            ("consultant BI", "Genève"),
            # Termes français
            ("ingénieur données", "Genève"),
            ("ingénieur IA", "Genève"),
            ("analyste données", "Genève"),
            ("développeur Python", "Genève"),
        ]
        
        headers = {
            "Content-Type": "application/json",
        }
        
        for keywords, location in searches:
            try:
                payload = {
                    "keywords": keywords,
                    "location": location,
                    "page": 1,
                }
                
                response = requests.post(
                    self.base_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                jobs = data.get("jobs", [])
                count = 0
                
                for job in jobs:
                    title = job.get("title", "").strip()
                    # Nettoyer le HTML du titre et description
                    title = title.replace("<b>", "").replace("</b>", "")
                    
                    desc = job.get("snippet", "")
                    desc = desc.replace("<b>", "").replace("</b>", "")
                    
                    job_location = job.get("location", location)
                    
                    # Filtre géographique — blacklist US + whitelist Suisse romande
                    loc_low = (job_location or "").lower()
                    comp_low = (job.get("company", "") or "").lower()
                    all_text = f"{loc_low} {title.lower()} {comp_low}"
                    
                    # REJETER si mot-clé US détecté
                    if any(t in all_text for t in [
                        "illinois", "indiana", "ohio", "texas", "california",
                        "arizona", "florida", "new york", "colorado",
                        ", il", ", pa", ", ma", ", ny", ", ca", ", tx",
                        "delnor", "northwestern medicine", "belterra",
                        "h&r block", "weedman", "marklund", "casino resort",
                    ]):
                        continue
                    
                    # ACCEPTER si indicateur Suisse romande détecté
                    ok = any(t in loc_low for t in [
                        "genev", "lausann", "nyon", "vaud", "suisse",
                        "switzerland", "schweiz", "swiss", "gland", "rolle",
                        "morges", "yverdon", "montreux", "vevey", "carouge",
                        "lancy", "meyrin", "vernier", "annemass", "ferney",
                        "eysins", "prangins", "renens", "pully", "coppet",
                    ])
                    if not ok:
                        continue
                    
                    offer = JobOffer(
                        title=title,
                        company=job.get("company", ""),
                        location=job.get("location", location),
                        description=desc,
                        url=job.get("link", ""),
                        salary=job.get("salary", None),
                        posted_date=job.get("updated", ""),
                        source="jooble",
                    )
                    
                    if offer.id not in seen_ids:
                        seen_ids.add(offer.id)
                        all_offers.append(offer)
                        count += 1
                
                if count > 0:
                    print(f"    ✅ Jooble: {count} offres pour '{keywords}' @ {location}")
                
            except Exception as e:
                print(f"    ⚠️  Jooble erreur pour '{keywords}': {e}")
        
        print(f"    📊 Jooble total: {len(all_offers)} offres uniques")
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
