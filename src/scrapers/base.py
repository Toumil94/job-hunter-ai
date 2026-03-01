"""
Base scraper interface — tous les scrapers héritent de cette classe.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import hashlib
import json


@dataclass
class JobOffer:
    """Représente une offre d'emploi standardisée."""
    
    # Identifiant unique (hash du titre + entreprise + source)
    id: str = ""
    
    # Infos principales
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    
    # Détails
    salary: Optional[str] = None
    contract_type: Optional[str] = None  # CDI, CDD, etc.
    experience_required: Optional[str] = None
    remote_policy: Optional[str] = None  # remote, hybrid, onsite
    posted_date: Optional[str] = None
    
    # Source
    source: str = ""  # adzuna, indeed, linkedin, etc.
    
    # Matching IA
    match_score: int = 0  # 0-100
    match_reasons: list = field(default_factory=list)
    
    # Statut
    status: str = "found"
    applied_date: Optional[str] = None
    followup_dates: list = field(default_factory=list)
    notes: str = ""
    
    # Cover letter générée
    cover_letter: Optional[str] = None
    
    def __post_init__(self):
        if not self.id and self.title and self.company:
            raw = f"{self.title}|{self.company}|{self.source}"
            self.id = hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "JobOffer":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BaseScraper(ABC):
    """Interface de base pour tous les scrapers d'offres."""
    
    def __init__(self, config: dict, profile: dict):
        self.config = config
        self.profile = profile
        self.source_name = "base"
    
    @abstractmethod
    def search(self, query: str, location: str, **kwargs) -> list[JobOffer]:
        """Cherche des offres et retourne une liste de JobOffer."""
        pass
    
    def search_all(self) -> list[JobOffer]:
        """Lance la recherche pour tous les titres de poste configurés."""
        all_offers = []
        seen_ids = set()
        
        target_titles = self.profile.get("job_search", {}).get("target_titles", [])
        
        # Use only unique, effective locations (avoid Geneva/Genève/Genf duplicates)
        search_locations = ["Geneva", "Lausanne"]
        
        for title in target_titles:
            for location in search_locations:
                try:
                    offers = self.search(title, location)
                    for offer in offers:
                        if offer.id not in seen_ids:
                            seen_ids.add(offer.id)
                            all_offers.append(offer)
                except Exception as e:
                    print(f"  ⚠️  Erreur scraping {self.source_name} "
                          f"({title} @ {location}): {e}")
        
        return all_offers
        
        return all_offers
