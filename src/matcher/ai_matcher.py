"""
🧠 AI Matcher — Utilise un LLM (Groq gratuit ou Claude) pour scorer chaque offre par rapport à ton profil.
C'est le cerveau du système.
"""

import os
import json
import time
from src.llm import complete
from src.scrapers.base import JobOffer


class AIMatcher:
    """Score et analyse chaque offre avec Claude."""
    
    def __init__(self, config: dict, profile: dict):
        self.config = config
        self.profile = profile
        self.model = config.get("apis", {}).get("anthropic", {}).get(
            "model", "claude-sonnet-4-20250514"
        )
        self.max_tokens = config.get("apis", {}).get("anthropic", {}).get(
            "max_tokens", 1500
        )
    
    def score_offers(self, offers: list[JobOffer]) -> list[JobOffer]:
        """Score toutes les offres et les trie par pertinence."""
        print(f"\n🧠 Analyse IA de {len(offers)} offres...")
        
        scored = []
        for i, offer in enumerate(offers):
            try:
                scored_offer = self._score_single(offer)
                scored.append(scored_offer)
                
                score_emoji = "🟢" if scored_offer.match_score >= 70 else (
                    "🟡" if scored_offer.match_score >= 50 else "🔴"
                )
                print(
                    f"  {score_emoji} [{scored_offer.match_score:3d}%] "
                    f"{scored_offer.title} @ {scored_offer.company}"
                )
                
                # Petit délai pour respecter les rate limits
                if i < len(offers) - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"  ⚠️  Erreur scoring {offer.title}: {e}")
                offer.match_score = 0
                scored.append(offer)
        
        # Trier par score décroissant
        scored.sort(key=lambda x: x.match_score, reverse=True)
        return scored
    
    def _score_single(self, offer: JobOffer) -> JobOffer:
        """Score une offre individuelle avec Claude."""
        
        profile_summary = self._build_profile_summary()
        
        prompt = f"""Tu es un expert en recrutement tech. Analyse cette offre d'emploi 
par rapport au profil du candidat et donne un score de matching.

## PROFIL DU CANDIDAT
{profile_summary}

## OFFRE D'EMPLOI
- **Titre**: {offer.title}
- **Entreprise**: {offer.company}
- **Localisation**: {offer.location}
- **Description**: {offer.description[:2000]}
{f'- **Salaire**: {offer.salary}' if offer.salary else ''}
{f'- **Type de contrat**: {offer.contract_type}' if offer.contract_type else ''}

## INSTRUCTIONS
Réponds UNIQUEMENT en JSON valide (pas de markdown, pas de backticks) :
{{
    "score": <int 0-100>,
    "reasons_match": ["raison 1", "raison 2", ...],
    "reasons_no_match": ["raison 1", ...],
    "red_flags": ["flag 1", ...],
    "recommendation": "apply" | "maybe" | "skip",
    "cover_letter_angle": "Angle suggéré pour la lettre de motivation en 1-2 phrases"
}}

Critères de scoring:
- 90-100: Match parfait (compétences, localisation, niveau)
- 70-89: Bon match (la plupart des critères correspondent)
- 50-69: Match partiel (quelques critères correspondent)
- 30-49: Match faible (peu de correspondance)
- 0-29: Pas pertinent
"""
        
        # Parser la réponse JSON
        response_text = complete(prompt, self.max_tokens, self.model)
        
        # Nettoyer si Claude ajoute des backticks
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
        
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback: essayer d'extraire le JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"score": 50, "reasons_match": ["Analyse non disponible"]}
        
        # Mettre à jour l'offre
        offer.match_score = result.get("score", 0)
        offer.match_reasons = result.get("reasons_match", [])
        
        # Stocker l'analyse complète dans les notes
        recommendation = result.get("recommendation", "unknown")
        red_flags = result.get("red_flags", [])
        no_match = result.get("reasons_no_match", [])
        cover_angle = result.get("cover_letter_angle", "")
        
        offer.notes = json.dumps({
            "recommendation": recommendation,
            "red_flags": red_flags,
            "reasons_no_match": no_match,
            "cover_letter_angle": cover_angle,
        }, ensure_ascii=False)
        
        return offer
    
    def _build_profile_summary(self) -> str:
        """Construit un résumé du profil pour le prompt."""
        personal = self.profile.get("personal", {})
        pro = self.profile.get("professional", {})
        search = self.profile.get("job_search", {})
        
        # Compiler toutes les compétences
        skills = pro.get("skills", {})
        all_skills = []
        for category, skill_list in skills.items():
            if isinstance(skill_list, list):
                all_skills.extend(skill_list)
        skills_str = ", ".join(all_skills)
        
        certs = ", ".join(pro.get("certifications", []))
        
        # Compiler les réalisations
        achievements = pro.get("key_achievements", [])
        if achievements and isinstance(achievements[0], dict):
            achievements_str = "\n".join(
                f"  - {a.get('description', '')} (Impact: {a.get('impact', 'N/A')})"
                for a in achievements
            )
        else:
            achievements_str = "\n".join(f"  - {a}" for a in achievements)
        
        # Langues
        languages = ", ".join(
            f"{l.get('language', '')} ({l.get('level', '')})"
            for l in personal.get("languages", [])
        )
        
        target_titles = ", ".join(search.get("target_titles", [])[:5])
        preferred_kw = ", ".join(search.get("preferred_keywords", []))
        exclude_kw = ", ".join(search.get("exclude_keywords", []))
        target_locations = ", ".join(search.get("locations", [])[:5])
        
        # Rôles tenus
        roles = ", ".join(
            r.get("title", "") for r in pro.get("roles", [])
        )
        
        return f"""
- **Titre actuel**: {pro.get('title', 'N/A')}
- **Expérience**: {pro.get('experience_years', 'N/A')} ans
- **Entreprise**: {pro.get('current_company', 'N/A')} ({pro.get('company_context', '')})
- **Rôles tenus**: {roles}
- **Formation**: {pro.get('education', [{}])[0].get('degree', 'N/A')} - {pro.get('education', [{}])[0].get('school', 'N/A')}
- **Certifications**: {certs}
- **Compétences**: {skills_str}
- **Réalisations clés**:
{achievements_str}
- **Langues**: {languages}
- **Localisation**: {personal.get('location', 'N/A')}
- **Disponibilité**: {personal.get('availability', 'N/A')}
- **Permis de travail**: {personal.get('work_permit', 'N/A')}
- **Zone recherchée**: {target_locations}
- **Postes ciblés**: {target_titles}
- **Mots-clés préférés**: {preferred_kw}
- **Mots-clés à exclure**: {exclude_kw}
"""


class CoverLetterGenerator:
    """Génère des lettres de motivation personnalisées avec Claude."""
    
    def __init__(self, config: dict, profile: dict):
        self.config = config
        self.profile = profile
        self.model = config.get("apis", {}).get("anthropic", {}).get(
            "model", "claude-sonnet-4-20250514"
        )
    
    def generate(self, offer: JobOffer) -> str:
        """Génère une lettre de motivation personnalisée pour une offre."""
        
        # Récupérer l'angle suggéré par le matcher
        cover_angle = ""
        try:
            notes = json.loads(offer.notes) if offer.notes else {}
            cover_angle = notes.get("cover_letter_angle", "")
        except (json.JSONDecodeError, TypeError):
            pass
        
        templates = self.profile.get("templates", {})
        # Détecter la langue de l'offre pour choisir le bon pitch
        desc_lower = (offer.description + offer.title).lower()
        is_english = any(w in desc_lower for w in ["the", "and", "with", "you", "we are", "looking for"])
        elevator_pitch = templates.get("elevator_pitch_en", "") if is_english else templates.get("elevator_pitch_fr", "")
        pro = self.profile.get("professional", {})
        achievements_raw = pro.get("key_achievements", [])
        # Support both dict and string formats
        achievements = [
            a.get("description", "") if isinstance(a, dict) else a
            for a in achievements_raw
        ]
        
        lang_instruction = "Rédige en ANGLAIS." if is_english else "Rédige en FRANÇAIS."
        
        prompt = f"""Tu es un expert en rédaction de lettres de motivation tech.
{lang_instruction}
Rédige une lettre de motivation percutante et personnalisée.

## CANDIDAT
{elevator_pitch}

Réalisations clés:
{chr(10).join(f'- {a}' for a in achievements[:5])}

## OFFRE
- **Poste**: {offer.title}
- **Entreprise**: {offer.company}
- **Localisation**: {offer.location}
- **Description**: {offer.description[:1500]}

## ANGLE SUGGÉRÉ
{cover_angle}

## CONSIGNES
- Maximum 300 mots
- Ton professionnel mais pas robotique
- Commence par une accroche percutante (PAS "Je me permets de...")
- Montre la valeur ajoutée concrète (chiffres, résultats)
- Fais le lien entre les réalisations du candidat et les besoins du poste
- Termine par un call-to-action concret
- Format: texte brut, pas de markdown
"""
        
        return complete(prompt, 1500, self.model)
    
    def generate_followup_message(
        self, offer: JobOffer, followup_number: int = 1
    ) -> str:
        """Génère un message de relance personnalisé."""
        
        tone_map = {
            1: "Poli et enthousiaste, rappelle ta candidature et ton intérêt",
            2: "Légèrement plus direct, ajoute une valeur nouvelle (article, projet...)",
            3: "Dernier message, bref et respectueux, laisse la porte ouverte",
        }
        
        tone = tone_map.get(followup_number, tone_map[1])
        
        prompt = f"""Rédige un message de relance #{followup_number} pour une candidature.

## CONTEXTE
- Poste: {offer.title} chez {offer.company}
- Candidature envoyée le: {offer.applied_date or 'récemment'}

## TON
{tone}

## CONSIGNES
- Maximum 100 mots
- Professionnel mais humain
- Format email court
- Inclus un objet d'email
- Format: OBJET: [objet]\n\n[corps du message]
"""
        
        return complete(prompt, 500, self.model)
