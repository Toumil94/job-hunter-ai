"""
Accès au modèle de langage, quel que soit le fournisseur.

- GROQ_API_KEY présent : Groq, niveau gratuit, modèle open source (par défaut openai/gpt-oss-120b).
- Sinon ANTHROPIC_API_KEY : Claude (payant).

Le niveau gratuit de Groq limite le nombre de requêtes et de tokens par minute :
en cas de dépassement (HTTP 429), on attend le délai indiqué puis on réessaie.
"""

import os
import time

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def provider() -> str:
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError("Aucune clé d'IA : renseigner GROQ_API_KEY (gratuit) ou ANTHROPIC_API_KEY.")


_announced = False


def complete(prompt: str, max_tokens: int = 1500, anthropic_model: str | None = None) -> str:
    """Envoie un prompt et renvoie le texte de la réponse."""
    global _announced
    if not _announced:
        # visible en un clic dans GitHub Actions (annotation)
        name = provider()
        model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL) if name == "groq" else (anthropic_model or "claude")
        print(f"::notice title=IA::Fournisseur {name}, modèle {model}", flush=True)
        _announced = True
    if provider() == "groq":
        return _groq(prompt, max_tokens)
    return _anthropic(prompt, max_tokens, anthropic_model)


def _groq(prompt: str, max_tokens: int, retries: int = 6) -> str:
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "temperature": 0.3,
    }
    if model.startswith("openai/gpt-oss"):
        # modèle de raisonnement : effort minimal et raisonnement masqué, pour économiser le quota
        body["reasoning_effort"] = "low"
        body["include_reasoning"] = False
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
    for attempt in range(retries):
        r = requests.post(GROQ_URL, json=body, headers=headers, timeout=90)
        if r.status_code == 429:
            wait = float(r.headers.get("retry-after", 0) or 0) or 10 * (attempt + 1)
            print(f"    ⏳ Limite gratuite atteinte, pause de {wait:.0f}s")
            time.sleep(min(wait, 90))
            continue
        if r.status_code == 400 and "include_reasoning" in body:
            # paramètres propres aux modèles de raisonnement refusés : on les retire
            body.pop("include_reasoning", None)
            body.pop("reasoning_effort", None)
            continue
        r.raise_for_status()
        return (r.json()["choices"][0]["message"].get("content") or "").strip()
    raise RuntimeError("Quota gratuit Groq épuisé pour le moment")


def _anthropic(prompt: str, max_tokens: int, model: str | None) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=model or "claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
