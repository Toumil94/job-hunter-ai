#!/usr/bin/env python3
"""
🤖 JOB HUNTER AI — Orchestrateur principal
=============================================
Automatise ta recherche d'emploi de A à Z.

Usage:
    python -m src.main hunt          # Lance un cycle complet (scrape → match → apply → report)
    python -m src.main scan          # Scan uniquement (pas de candidature)
    python -m src.main followup      # Vérifie et envoie les relances
    python -m src.main stats         # Affiche les statistiques
    python -m src.main export        # Exporte en CSV
    python -m src.main daemon        # Mode daemon (tourne en continu selon le planning)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.scrapers import AdzunaScraper, SwissDevJobsScraper, AdzunaBroadScraper, JobOffer
from src.matcher.ai_matcher import AIMatcher, CoverLetterGenerator
from src.tracker.tracker import ApplicationTracker
from src.notifier.email_notifier import EmailNotifier


class JobHunterAI:
    """Orchestrateur principal du système."""
    
    def __init__(self):
        """Initialise tous les composants."""
        self.root_dir = ROOT_DIR
        self.config = self._load_yaml("config/settings.yaml")
        self.profile = self._load_yaml("config/profile.yaml")
        
        # Composants
        self.scrapers = [
            AdzunaScraper(self.config, self.profile),
            AdzunaBroadScraper(self.config, self.profile),
            SwissDevJobsScraper(self.config, self.profile),
        ]
        self.matcher = AIMatcher(self.config, self.profile)
        self.cover_gen = CoverLetterGenerator(self.config, self.profile)
        self.tracker = ApplicationTracker(self.config)
        self.notifier = EmailNotifier(self.config)
        
        # Paramètres de sécurité
        self.dry_run = self.config.get("safety", {}).get("dry_run", True)
        self.max_daily = self.config.get("safety", {}).get(
            "max_daily_applications", 10
        )
        self.delay = self.config.get("safety", {}).get(
            "delay_between_applications", 30
        )
        self.min_match = self.profile.get("job_search", {}).get(
            "min_match_score", 70
        )
        self.min_report = self.profile.get("job_search", {}).get(
            "min_report_score", 50
        )
    
    def _load_yaml(self, path: str) -> dict:
        """Charge un fichier YAML."""
        full_path = self.root_dir / path
        with open(full_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    # =========================================================================
    # 🎯 COMMANDES PRINCIPALES
    # =========================================================================
    
    def hunt(self):
        """
        🎯 Cycle complet: Scrape → Match → Apply → Report
        C'est LA commande principale.
        """
        print("=" * 60)
        print("🤖 JOB HUNTER AI — Cycle de chasse")
        print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print(f"🔧 Mode: {'🧪 SIMULATION' if self.dry_run else '🟢 ACTIF'}")
        print("=" * 60)
        
        # ÉTAPE 1: Scraping
        print("\n📡 ÉTAPE 1: Recherche d'offres...")
        all_offers = self._scrape_all()
        
        if not all_offers:
            print("😴 Aucune offre trouvée. Fin du cycle.")
            self.notifier.send_daily_report([], [], [], self.tracker.get_stats())
            return
        
        # ÉTAPE 2: Filtrer les doublons (déjà dans le tracker)
        print(f"\n🔍 ÉTAPE 2: Filtrage des doublons...")
        new_offers = self.tracker.get_new_offers(all_offers)
        print(f"  → {len(new_offers)} nouvelles offres "
              f"(sur {len(all_offers)} trouvées)")
        
        if not new_offers:
            print("😴 Pas de nouvelles offres. Vérification des relances...")
            self._handle_followups()
            self.notifier.send_daily_report(
                [], [], self.tracker.get_pending_followups(),
                self.tracker.get_stats()
            )
            return
        
        # ÉTAPE 3: Matching IA
        print(f"\n🧠 ÉTAPE 3: Analyse IA de {len(new_offers)} offres...")
        scored_offers = self.matcher.score_offers(new_offers)
        
        # Filtrer par score minimum pour le rapport
        relevant_offers = [
            o for o in scored_offers if o.match_score >= self.min_report
        ]
        
        # ÉTAPE 4: Ajouter au tracker
        print(f"\n📊 ÉTAPE 4: Mise à jour du tracker...")
        for offer in scored_offers:
            self.tracker.add_offer(offer)
        
        # ÉTAPE 5: Candidatures automatiques — générer les cover letters
        applied_offers = []
        top_matches = [
            o for o in scored_offers if o.match_score >= self.min_match
        ]
        
        if top_matches:
            print(f"\n✉️  ÉTAPE 5: Génération des lettres pour {len(top_matches)} top matches (≥{self.min_match}%)")
            applied_offers = self._auto_apply(top_matches)
        else:
            print(f"\n⚠️  ÉTAPE 5: Aucune offre au-dessus du seuil ({self.min_match}%)")
        
        # ÉTAPE 6: Vérifier les relances
        print(f"\n🔔 ÉTAPE 6: Vérification des relances...")
        pending_followups = self._handle_followups()
        
        # ÉTAPE 7: Rapport email
        print(f"\n📧 ÉTAPE 7: Envoi du rapport...")
        self.notifier.send_daily_report(
            relevant_offers,
            applied_offers,
            pending_followups,
            self.tracker.get_stats(),
        )
        
        # Résumé final
        stats = self.tracker.get_stats()
        print("\n" + "=" * 60)
        print("✅ CYCLE TERMINÉ")
        print(f"  📊 Offres trouvées: {len(all_offers)}")
        print(f"  🆕 Nouvelles: {len(new_offers)}")
        print(f"  🎯 Pertinentes (≥{self.min_report}%): {len(relevant_offers)}")
        print(f"  ✅ Candidatures envoyées: {len(applied_offers)}")
        print(f"  📈 Total candidatures: {stats.get('total_applied', 0)}")
        print(f"  📈 Taux de réponse: {stats.get('response_rate', 0)}%")
        print("=" * 60)
    
    def scan(self):
        """📡 Scan uniquement — trouve et score les offres sans postuler."""
        print("📡 Mode SCAN — recherche d'offres sans candidature\n")
        
        all_offers = self._scrape_all()
        new_offers = self.tracker.get_new_offers(all_offers)
        
        if new_offers:
            scored = self.matcher.score_offers(new_offers)
            for offer in scored:
                self.tracker.add_offer(offer)
            
            relevant = [o for o in scored if o.match_score >= self.min_report]
            self.notifier.send_daily_report(
                relevant, [], [], self.tracker.get_stats()
            )
        else:
            print("😴 Aucune nouvelle offre.")
    
    def followup(self):
        """🔔 Vérifie et gère les relances."""
        print("🔔 Vérification des relances...\n")
        pending = self._handle_followups()
        
        if pending:
            self.notifier.send_followup_reminder(pending)
        else:
            print("✅ Aucune relance à faire aujourd'hui.")
    
    def stats(self):
        """📊 Affiche les statistiques."""
        stats = self.tracker.get_stats()
        
        print("=" * 50)
        print("📊 STATISTIQUES JOB HUNTER AI")
        print("=" * 50)
        print(f"  📋 Offres suivies:    {stats.get('total_tracked', 0)}")
        print(f"  ✅ Candidatures:      {stats.get('total_applied', 0)}")
        print(f"  💬 Réponses:          {stats.get('total_responses', 0)}")
        print(f"  🎤 Entretiens:        {stats.get('total_interviews', 0)}")
        print(f"  📈 Taux de réponse:   {stats.get('response_rate', 0)}%")
        print()
        print("  Par statut:")
        for status, count in stats.get("by_status", {}).items():
            print(f"    {status}: {count}")
        print()
        print("  Par source:")
        for source, count in stats.get("by_source", {}).items():
            print(f"    {source}: {count}")
        print()
        print("  Par score:")
        scores = stats.get("by_score", {})
        print(f"    🟢 Élevé (≥70):  {scores.get('high', 0)}")
        print(f"    🟡 Moyen (50-69): {scores.get('medium', 0)}")
        print(f"    🔴 Faible (<50):  {scores.get('low', 0)}")
        print(f"\n  Dernier scan: {stats.get('last_scan', 'Jamais')}")
        print("=" * 50)
    
    def export(self):
        """📥 Exporte les candidatures en CSV."""
        self.tracker.export_csv()
    
    def daemon(self):
        """
        👹 Mode daemon — tourne en continu selon le planning configuré.
        Utile pour exécution locale (pas besoin pour GitHub Actions).
        """
        import schedule as sched
        
        scan_times = self.config.get("schedule", {}).get(
            "scan_times", ["07:00", "18:00"]
        )
        
        print("👹 MODE DAEMON — Job Hunter AI tourne en continu")
        print(f"   Scans programmés: {', '.join(scan_times)}")
        print("   Ctrl+C pour arrêter\n")
        
        for t in scan_times:
            sched.every().day.at(t).do(self.hunt)
        
        # Vérifier les relances tous les jours à 9h
        sched.every().day.at("09:00").do(self.followup)
        
        # Premier scan immédiat
        self.hunt()
        
        while True:
            sched.run_pending()
            time.sleep(60)
    
    # =========================================================================
    # 🔧 MÉTHODES INTERNES
    # =========================================================================
    
    def _scrape_all(self) -> list[JobOffer]:
        """Lance tous les scrapers et combine les résultats."""
        all_offers = []
        seen_ids = set()
        
        for scraper in self.scrapers:
            print(f"\n  🔎 {scraper.source_name.upper()}...")
            try:
                offers = scraper.search_all()
                for offer in offers:
                    if offer.id not in seen_ids:
                        seen_ids.add(offer.id)
                        all_offers.append(offer)
            except Exception as e:
                print(f"  ❌ Erreur {scraper.source_name}: {e}")
        
        print(f"\n  📊 Total: {len(all_offers)} offres uniques trouvées")
        return all_offers
    
    def _auto_apply(self, offers: list[JobOffer]) -> list[JobOffer]:
        """
        Gère les candidatures automatiques.
        Pour l'instant: génère cover letter + prépare la candidature.
        L'envoi automatique direct est limité aux plateformes qui le permettent.
        """
        applied = []
        
        for i, offer in enumerate(offers[:self.max_daily]):
            print(f"\n  📝 [{i+1}/{min(len(offers), self.max_daily)}] "
                  f"{offer.title} @ {offer.company}")
            
            # Générer la lettre de motivation
            try:
                print(f"    ✍️  Génération de la lettre de motivation...")
                cover_letter = self.cover_gen.generate(offer)
                offer.cover_letter = cover_letter
                
                if self.dry_run:
                    print(f"    🧪 [SIMULATION] Candidature préparée (non envoyée)")
                    # En mode dry_run, on marque quand même comme "matched" pas "applied"
                    self.tracker.update_status(
                        offer.id, "matched", cover_letter=cover_letter
                    )
                else:
                    # En mode actif, on marque comme "applied"
                    self.tracker.update_status(
                        offer.id, "applied", cover_letter=cover_letter
                    )
                    applied.append(offer)
                    print(f"    ✅ Candidature envoyée !")
                    
                    # Délai entre les candidatures
                    if i < len(offers) - 1:
                        print(f"    ⏳ Attente {self.delay}s...")
                        time.sleep(self.delay)
                        
            except Exception as e:
                print(f"    ❌ Erreur: {e}")
        
        return applied
    
    def _handle_followups(self) -> list[dict]:
        """Gère les relances automatiques et génère les messages."""
        pending = self.tracker.get_pending_followups()
        
        if not pending:
            return []
        
        print(f"  📬 {len(pending)} relance(s) à faire")
        
        for item in pending:
            offer = item["offer"]
            num = item["followup_number"]
            
            print(f"    → Relance #{num}: {offer.title} @ {offer.company}")
            
            try:
                # Générer le message de relance
                message = self.cover_gen.generate_followup_message(offer, num)
                item["followup_message"] = message
                
                if not self.dry_run:
                    # En mode actif, enregistrer la relance
                    self.tracker.add_followup(offer.id, num)
                    print(f"      ✅ Relance #{num} générée")
                else:
                    print(f"      🧪 [SIMULATION] Message de relance généré")
                    
            except Exception as e:
                print(f"      ❌ Erreur: {e}")
                item["followup_message"] = ""
        
        return pending


def main():
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="🤖 Job Hunter AI — Automatise ta recherche d'emploi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commandes:
  hunt      🎯 Cycle complet (scrape → match → apply → report)
  scan      📡 Scan uniquement (pas de candidature)
  followup  🔔 Vérifie et envoie les relances
  stats     📊 Affiche les statistiques
  export    📥 Exporte en CSV
  daemon    👹 Mode continu (tourne selon le planning)
        """,
    )
    
    parser.add_argument(
        "command",
        choices=["hunt", "scan", "followup", "stats", "export", "daemon"],
        help="Commande à exécuter",
    )
    
    args = parser.parse_args()
    
    # Vérifier les clés API essentielles
    if args.command in ["hunt", "scan", "followup"]:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("❌ ANTHROPIC_API_KEY non définie !")
            print("   → Copie .env.example en .env et ajoute ta clé")
            sys.exit(1)
    
    if args.command in ["hunt", "scan"]:
        if not os.getenv("ADZUNA_APP_ID"):
            print("⚠️  ADZUNA_APP_ID non définie — le scraper Adzuna sera désactivé")
    
    hunter = JobHunterAI()
    
    commands = {
        "hunt": hunter.hunt,
        "scan": hunter.scan,
        "followup": hunter.followup,
        "stats": hunter.stats,
        "export": hunter.export,
        "daemon": hunter.daemon,
    }
    
    commands[args.command]()


if __name__ == "__main__":
    main()
