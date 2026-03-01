"""
📊 Application Tracker — Suivi de toutes tes candidatures.
Stockage local en JSON (simple, gratuit, pas de DB nécessaire).
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from src.scrapers.base import JobOffer


class ApplicationTracker:
    """Gère le suivi des candidatures et les relances."""
    
    def __init__(self, config: dict):
        self.config = config
        self.db_path = config.get("tracker", {}).get(
            "database_file", "data/applications.json"
        )
        self.followup_config = config.get("schedule", {}).get("followup_days", {})
        self._ensure_db()
    
    def _ensure_db(self):
        """Crée le fichier de DB s'il n'existe pas."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            self._save_db({
                "applications": {},
                "stats": {
                    "total_found": 0,
                    "total_applied": 0,
                    "total_responses": 0,
                    "total_interviews": 0,
                },
                "last_scan": None,
            })
    
    def _load_db(self) -> dict:
        """Charge la base de données."""
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_db(self, data: dict):
        """Sauvegarde la base de données."""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def is_already_tracked(self, offer_id: str) -> bool:
        """Vérifie si une offre est déjà dans le tracker."""
        db = self._load_db()
        return offer_id in db["applications"]
    
    def add_offer(self, offer: JobOffer) -> bool:
        """Ajoute une offre au tracker. Retourne False si déjà présente."""
        db = self._load_db()
        
        if offer.id in db["applications"]:
            return False
        
        db["applications"][offer.id] = offer.to_dict()
        db["stats"]["total_found"] += 1
        db["last_scan"] = datetime.now().isoformat()
        
        self._save_db(db)
        return True
    
    def update_status(self, offer_id: str, status: str, **kwargs):
        """Met à jour le statut d'une candidature."""
        db = self._load_db()
        
        if offer_id not in db["applications"]:
            return
        
        app = db["applications"][offer_id]
        old_status = app["status"]
        app["status"] = status
        
        # Mettre à jour les stats
        if status == "applied" and old_status != "applied":
            app["applied_date"] = datetime.now().isoformat()
            db["stats"]["total_applied"] += 1
        elif status == "response":
            db["stats"]["total_responses"] += 1
        elif status == "interview":
            db["stats"]["total_interviews"] += 1
        
        # Mettre à jour les champs supplémentaires
        for key, value in kwargs.items():
            if key in app:
                app[key] = value
        
        self._save_db(db)
    
    def add_followup(self, offer_id: str, followup_number: int):
        """Enregistre une relance."""
        db = self._load_db()
        
        if offer_id not in db["applications"]:
            return
        
        app = db["applications"][offer_id]
        app["followup_dates"].append({
            "number": followup_number,
            "date": datetime.now().isoformat(),
        })
        app["status"] = f"followup_{followup_number}"
        
        self._save_db(db)
    
    def get_pending_followups(self) -> list[dict]:
        """
        Retourne les candidatures qui nécessitent une relance.
        Basé sur les délais configurés dans settings.yaml.
        """
        db = self._load_db()
        now = datetime.now()
        pending = []
        
        first_days = self.followup_config.get("first_followup", 7)
        second_days = self.followup_config.get("second_followup", 14)
        final_days = self.followup_config.get("final_followup", 21)
        
        for offer_id, app in db["applications"].items():
            if app["status"] in ["rejected", "interview", "offer", "response"]:
                continue
            
            if not app.get("applied_date"):
                continue
            
            applied_date = datetime.fromisoformat(app["applied_date"])
            days_since = (now - applied_date).days
            
            followup_count = len(app.get("followup_dates", []))
            
            needs_followup = False
            followup_number = 0
            
            if followup_count == 0 and days_since >= first_days:
                needs_followup = True
                followup_number = 1
            elif followup_count == 1 and days_since >= second_days:
                needs_followup = True
                followup_number = 2
            elif followup_count == 2 and days_since >= final_days:
                needs_followup = True
                followup_number = 3
            
            if needs_followup:
                pending.append({
                    "offer": JobOffer.from_dict(app),
                    "followup_number": followup_number,
                    "days_since_applied": days_since,
                })
        
        return pending
    
    def get_new_offers(self, offers: list[JobOffer]) -> list[JobOffer]:
        """Filtre les offres pour ne garder que les nouvelles."""
        db = self._load_db()
        return [o for o in offers if o.id not in db["applications"]]
    
    def get_stats(self) -> dict:
        """Retourne les statistiques globales."""
        db = self._load_db()
        stats = db["stats"].copy()
        
        # Calculer des stats supplémentaires
        apps = db["applications"]
        stats["total_tracked"] = len(apps)
        stats["by_status"] = {}
        stats["by_source"] = {}
        stats["by_score"] = {"high": 0, "medium": 0, "low": 0}
        
        for app in apps.values():
            # Par statut
            status = app.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # Par source
            source = app.get("source", "unknown")
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
            
            # Par score
            score = app.get("match_score", 0)
            if score >= 70:
                stats["by_score"]["high"] += 1
            elif score >= 50:
                stats["by_score"]["medium"] += 1
            else:
                stats["by_score"]["low"] += 1
        
        # Taux de réponse
        if stats["total_applied"] > 0:
            stats["response_rate"] = round(
                (stats["total_responses"] / stats["total_applied"]) * 100, 1
            )
        else:
            stats["response_rate"] = 0
        
        stats["last_scan"] = db.get("last_scan")
        
        return stats
    
    def get_all_applications(self) -> list[JobOffer]:
        """Retourne toutes les candidatures."""
        db = self._load_db()
        return [
            JobOffer.from_dict(app) 
            for app in db["applications"].values()
        ]
    
    def export_csv(self, filepath: str = "data/applications_export.csv"):
        """Exporte les candidatures en CSV."""
        import csv
        
        db = self._load_db()
        
        if not db["applications"]:
            print("Aucune candidature à exporter.")
            return
        
        fieldnames = [
            "id", "title", "company", "location", "match_score",
            "status", "source", "url", "applied_date", "salary",
        ]
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for app in db["applications"].values():
                row = {k: app.get(k, "") for k in fieldnames}
                writer.writerow(row)
        
        print(f"✅ Export CSV: {filepath}")
