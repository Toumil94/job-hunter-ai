"""
📧 Email Notifier — Envoie les rapports quotidiens par email.
Utilise Gmail SMTP (gratuit).
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from src.scrapers.base import JobOffer


class EmailNotifier:
    """Envoie des rapports email sur les candidatures."""
    
    def __init__(self, config: dict):
        self.config = config
        email_config = config.get("email", {})
        self.smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = email_config.get("smtp_port", 587)
        self.sender = os.getenv("EMAIL_SENDER", "")
        self.password = os.getenv("EMAIL_APP_PASSWORD", "")
        self.recipient = os.getenv("EMAIL_RECIPIENT", self.sender)
    
    def send_daily_report(
        self,
        new_offers: list[JobOffer],
        applied_offers: list[JobOffer],
        pending_followups: list[dict],
        stats: dict,
    ):
        """Envoie le rapport quotidien complet."""
        
        subject = self._build_subject(new_offers, applied_offers)
        html_body = self._build_html_report(
            new_offers, applied_offers, pending_followups, stats
        )
        
        self._send_email(subject, html_body)
        print(f"📧 Rapport envoyé à {self.recipient}")
    
    def send_followup_reminder(self, followups: list[dict]):
        """Envoie un rappel pour les relances à faire."""
        if not followups:
            return
        
        subject = f"🔔 {len(followups)} relance(s) à faire aujourd'hui"
        
        html = "<h2>Relances à envoyer</h2><ul>"
        for f in followups:
            offer = f["offer"]
            html += (
                f"<li><strong>{offer.title}</strong> @ {offer.company} "
                f"— Relance #{f['followup_number']} "
                f"(candidature il y a {f['days_since_applied']} jours)"
                f"<br><a href='{offer.url}'>Voir l'offre</a></li>"
            )
        html += "</ul>"
        
        self._send_email(subject, html)
    
    def _build_subject(
        self, new_offers: list[JobOffer], applied_offers: list[JobOffer]
    ) -> str:
        """Construit le sujet de l'email."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        parts = []
        
        if new_offers:
            high_match = sum(1 for o in new_offers if o.match_score >= 70)
            parts.append(f"🎯 {high_match} top match(es)")
        
        if applied_offers:
            parts.append(f"✅ {len(applied_offers)} candidature(s)")
        
        if not parts:
            parts.append("📊 Rapport")
        
        return f"Job Hunter AI — {' | '.join(parts)} — {now}"
    
    def _build_html_report(
        self,
        new_offers: list[JobOffer],
        applied_offers: list[JobOffer],
        pending_followups: list[dict],
        stats: dict,
    ) -> str:
        """Construit le rapport HTML complet."""
        
        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
           max-width: 700px; margin: 0 auto; padding: 20px; color: #1a1a1a; 
           background: #f8f9fa; }}
    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
               color: white; padding: 25px; border-radius: 12px; margin-bottom: 20px; }}
    .header h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
    .header p {{ margin: 0; opacity: 0.9; font-size: 14px; }}
    .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); 
                   gap: 10px; margin-bottom: 20px; }}
    .stat-card {{ background: white; padding: 15px; border-radius: 10px; 
                  text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .stat-number {{ font-size: 28px; font-weight: bold; color: #667eea; }}
    .stat-label {{ font-size: 12px; color: #666; margin-top: 4px; }}
    .section {{ background: white; border-radius: 10px; padding: 20px; 
                margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .section h2 {{ margin-top: 0; color: #333; font-size: 18px; 
                   border-bottom: 2px solid #667eea; padding-bottom: 8px; }}
    .job-card {{ border-left: 4px solid #667eea; padding: 12px 15px; 
                 margin: 10px 0; background: #f8f9ff; border-radius: 0 8px 8px 0; }}
    .job-card.high {{ border-left-color: #22c55e; background: #f0fdf4; }}
    .job-card.medium {{ border-left-color: #f59e0b; background: #fffbeb; }}
    .job-card.low {{ border-left-color: #ef4444; background: #fef2f2; }}
    .job-title {{ font-weight: bold; font-size: 15px; margin-bottom: 4px; }}
    .job-meta {{ font-size: 13px; color: #666; }}
    .score-badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px; 
                    font-size: 12px; font-weight: bold; color: white; }}
    .score-high {{ background: #22c55e; }}
    .score-medium {{ background: #f59e0b; }}
    .score-low {{ background: #ef4444; }}
    .reasons {{ font-size: 12px; color: #555; margin-top: 6px; }}
    a {{ color: #667eea; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 20px; }}
    .followup-item {{ padding: 10px; margin: 8px 0; background: #fff7ed; 
                      border-left: 4px solid #f59e0b; border-radius: 0 8px 8px 0; }}
</style>
</head>
<body>

<div class="header">
    <h1>🤖 Job Hunter AI — Rapport</h1>
    <p>{now}</p>
</div>

<!-- STATS -->
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-number">{stats.get('total_tracked', 0)}</div>
        <div class="stat-label">Offres suivies</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{stats.get('total_applied', 0)}</div>
        <div class="stat-label">Candidatures</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{stats.get('total_responses', 0)}</div>
        <div class="stat-label">Réponses</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{stats.get('response_rate', 0)}%</div>
        <div class="stat-label">Taux réponse</div>
    </div>
</div>
"""
        
        # Section: Nouvelles offres matchées
        if new_offers:
            high_match = [o for o in new_offers if o.match_score >= 70]
            medium_match = [o for o in new_offers if 50 <= o.match_score < 70]
            
            html += '<div class="section">'
            html += f"<h2>🎯 Nouvelles offres ({len(new_offers)})</h2>"
            
            for offer in new_offers:
                score_class = (
                    "high" if offer.match_score >= 70 
                    else ("medium" if offer.match_score >= 50 else "low")
                )
                score_badge_class = f"score-{score_class}"
                
                reasons = ", ".join(offer.match_reasons[:3]) if offer.match_reasons else ""
                
                html += f"""
                <div class="job-card {score_class}">
                    <div class="job-title">
                        <span class="score-badge {score_badge_class}">{offer.match_score}%</span>
                        &nbsp; {offer.title}
                    </div>
                    <div class="job-meta">
                        🏢 {offer.company} &nbsp;|&nbsp; 
                        📍 {offer.location} &nbsp;|&nbsp; 
                        📅 {offer.posted_date or 'N/A'}
                        {f' &nbsp;|&nbsp; 💰 {offer.salary}' if offer.salary else ''}
                    </div>
                    <div class="reasons">✨ {reasons}</div>
                    <div style="margin-top: 8px;">
                        <a href="{offer.url}" style="background: #667eea; color: white; 
                           padding: 6px 16px; border-radius: 6px; text-decoration: none;
                           font-size: 13px; font-weight: bold;">
                           👉 Postuler maintenant
                        </a>
                    </div>
                """
                
                # Ajouter la lettre de motivation si disponible (top matches)
                if offer.cover_letter and offer.match_score >= 70:
                    escaped_letter = offer.cover_letter.replace('\n', '<br>')
                    html += f"""
                    <details style="margin-top: 10px; background: #f0f4ff; 
                             padding: 12px; border-radius: 8px;">
                        <summary style="cursor: pointer; font-weight: bold; 
                                 color: #667eea; font-size: 14px;">
                            ✉️ Lettre de motivation personnalisée (cliquer pour ouvrir)
                        </summary>
                        <div style="margin-top: 10px; font-size: 13px; 
                             line-height: 1.6; color: #333; white-space: pre-line;">
                            {escaped_letter}
                        </div>
                        <div style="margin-top: 8px; text-align: right;">
                            <span style="font-size: 11px; color: #999;">
                                📋 Copie ce texte et colle-le dans ta candidature
                            </span>
                        </div>
                    </details>
                    """
                
                html += "</div>"
            
            html += "</div>"
        
        # Section: Candidatures envoyées
        if applied_offers:
            html += '<div class="section">'
            html += f"<h2>✅ Candidatures envoyées ({len(applied_offers)})</h2>"
            
            for offer in applied_offers:
                html += f"""
                <div class="job-card high">
                    <div class="job-title">{offer.title}</div>
                    <div class="job-meta">
                        🏢 {offer.company} &nbsp;|&nbsp; 📍 {offer.location}
                    </div>
                    <div style="margin-top: 6px;">
                        <a href="{offer.url}">Voir l'offre →</a>
                    </div>
                </div>
                """
            
            html += "</div>"
        
        # Section: Relances à faire
        if pending_followups:
            html += '<div class="section">'
            html += f"<h2>🔔 Relances à faire ({len(pending_followups)})</h2>"
            
            for f in pending_followups:
                offer = f["offer"]
                followup_msg = f.get("followup_message", "")
                
                html += f"""
                <div class="followup-item">
                    <strong>{offer.title}</strong> @ {offer.company}<br>
                    <span style="font-size: 13px; color: #666;">
                        Relance #{f['followup_number']} — 
                        Candidature il y a {f['days_since_applied']} jours
                    </span><br>
                    <a href="{offer.url}">Voir l'offre →</a>
                """
                
                if followup_msg:
                    escaped_msg = followup_msg.replace('\n', '<br>')
                    html += f"""
                    <details style="margin-top: 8px; background: #fff7ed; 
                             padding: 10px; border-radius: 6px;">
                        <summary style="cursor: pointer; font-weight: bold; 
                                 color: #f59e0b; font-size: 13px;">
                            ✉️ Message de relance pré-rédigé (cliquer pour ouvrir)
                        </summary>
                        <div style="margin-top: 8px; font-size: 13px; 
                             line-height: 1.5; color: #333; white-space: pre-line;">
                            {escaped_msg}
                        </div>
                    </details>
                    """
                
                html += "</div>"
            
            html += "</div>"
        
        # Rien de nouveau
        if not new_offers and not applied_offers and not pending_followups:
            html += """
            <div class="section" style="text-align: center; padding: 30px;">
                <p style="font-size: 16px; color: #666;">
                    😴 Pas de nouvelles offres pertinentes aujourd'hui.<br>
                    Le prochain scan est programmé automatiquement.
                </p>
            </div>
            """
        
        html += """
<div class="footer">
    <p>🤖 Généré automatiquement par Job Hunter AI<br>
    Mode: {mode}</p>
</div>
</body>
</html>
""".format(
            mode="🧪 SIMULATION" 
            if self.config.get("safety", {}).get("dry_run", True)
            else "🟢 ACTIF"
        )
        
        return html
    
    def _send_email(self, subject: str, html_body: str):
        """Envoie un email via SMTP."""
        if not self.sender or not self.password:
            print("⚠️  Email non configuré — rapport affiché en console uniquement")
            print(f"    Sujet: {subject}")
            return
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Job Hunter AI <{self.sender}>"
        msg["To"] = self.recipient
        
        # Version texte simple (fallback)
        text_part = MIMEText(
            "Voir la version HTML de ce rapport.", "plain", "utf-8"
        )
        html_part = MIMEText(html_body, "html", "utf-8")
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")
            print("   Vérifie ta configuration email dans .env")
            raise
