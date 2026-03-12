import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from crewai import Agent, Task, Crew, Process
from groq import Groq
from supabase import create_client

# ─────────────────────────────────────────
# CONFIGURATION — clés depuis les variables d'environnement
# ─────────────────────────────────────────
GROQ_API_KEY    = os.environ.get("GROQ_API_KEY")
SUPABASE_URL    = os.environ.get("SUPABASE_URL")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY")
GMAIL_USER      = os.environ.get("GMAIL_USER", "inonbkrs@gmail.com")
GMAIL_PASSWORD  = os.environ.get("GMAIL_PASSWORD")
GROQ_MODEL      = "llama-3.3-70b-versatile"

# Clients
groq_client     = Groq(api_key=GROQ_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────
# FONCTION LLM via Groq
# ─────────────────────────────────────────
def groq_llm(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()

# ─────────────────────────────────────────
# AGENTS
# ─────────────────────────────────────────

def agent_analyse_marche(niche: str) -> str:
    prompt = f"""
Tu es un expert en analyse de marché. Analyse la niche suivante : {niche}.
Réponds en français avec :
1. Taille du marché et tendances
2. Problèmes principaux des clients
3. Concurrents principaux
4. Opportunités à saisir
5. Revenus estimés mensuels pour une offre IA (fourchette réaliste)
"""
    return groq_llm(prompt)

def agent_generation_prospects(niche: str, analyse: str) -> str:
    prompt = f"""
Tu es un expert en génération de leads B2B. Niche : {niche}.
Contexte marché : {analyse[:500]}

Génère 5 profils de prospects idéaux avec :
- Nom fictif de l'entreprise
- Secteur précis
- Problème principal
- Budget estimé
- Email fictif professionnel (format: prenom.nom@entreprise.fr)
Format JSON lisible.
"""
    return groq_llm(prompt)

def agent_email_vente(niche: str, analyse: str) -> str:
    prompt = f"""
Tu es un copywriter expert en cold email B2B. Niche : {niche}.
Contexte : {analyse[:400]}

Écris un email de vente percutant (cold email) pour proposer une solution IA automatisée.
- Objet accrocheur
- Corps court (150 mots max)
- CTA clair
- Ton professionnel mais humain
- En français
"""
    return groq_llm(prompt)

def agent_plan_90_jours(niche: str) -> str:
    prompt = f"""
Tu es un consultant business. Crée un plan d'action 90 jours pour lancer une offre IA dans la niche : {niche}.
Structure :
- Mois 1 : Fondations (semaines 1-4)
- Mois 2 : Lancement (semaines 5-8)  
- Mois 3 : Croissance (semaines 9-12)
KPIs à suivre chaque semaine.
Sois concret et actionnable.
"""
    return groq_llm(prompt)

# ─────────────────────────────────────────
# SAUVEGARDE SUPABASE
# ─────────────────────────────────────────

def sauvegarder_rapport(niche, analyse, prospects, email_vente, plan_90j):
    data = {
        "niche":           niche,
        "contenu":         analyse,
        "revenus_estimes": "5 000 – 15 000 € / mois",
        "prospects":       prospects,
        "emails_vente":    email_vente,
        "plan_90_jours":   plan_90j,
        "kpis":            "CA mensuel, leads contactés, taux de réponse, contrats signés",
        "date_creation":   datetime.datetime.utcnow().isoformat(),
    }
    result = supabase_client.table("rapports").insert(data).execute()
    print(f"✅ Rapport sauvegardé dans Supabase — ID: {result.data[0]['id'] if result.data else 'N/A'}")
    return result

# ─────────────────────────────────────────
# ENVOI EMAIL GMAIL
# ─────────────────────────────────────────

def envoyer_email_rapport(niche, analyse, prospects, email_vente, plan_90j):
    if not GMAIL_PASSWORD:
        print("⚠️  GMAIL_PASSWORD non configuré — email ignoré")
        return

    sujet = f"🤖 Rapport IA — Niche : {niche} | {datetime.date.today()}"
    corps = f"""
=== RAPPORT BUSINESS IA ===
Niche : {niche}
Date  : {datetime.date.today()}

📊 ANALYSE MARCHÉ
{analyse}

👥 PROSPECTS GÉNÉRÉS
{prospects}

📧 EMAIL DE VENTE
{email_vente}

📅 PLAN 90 JOURS
{plan_90j}
"""
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = sujet
    msg.attach(MIMEText(corps, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        print(f"✅ Email envoyé à {GMAIL_USER}")
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")

# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────

def lancer_pipeline(niche: str):
    print(f"\n🚀 Lancement du pipeline pour la niche : {niche}")
    print("─" * 50)

    print("🔍 Agent 1 — Analyse de marché...")
    analyse = agent_analyse_marche(niche)

    print("👥 Agent 2 — Génération de prospects...")
    prospects = agent_generation_prospects(niche, analyse)

    print("📧 Agent 3 — Rédaction email de vente...")
    email_vente = agent_email_vente(niche, analyse)

    print("📅 Agent 4 — Plan 90 jours...")
    plan_90j = agent_plan_90_jours(niche)

    print("💾 Sauvegarde dans Supabase...")
    sauvegarder_rapport(niche, analyse, prospects, email_vente, plan_90j)

    print("📬 Envoi email de rapport...")
    envoyer_email_rapport(niche, analyse, prospects, email_vente, plan_90j)

    print(f"\n✅ Pipeline terminé pour : {niche}")
    return {
        "niche":      niche,
        "analyse":    analyse,
        "prospects":  prospects,
        "email":      email_vente,
        "plan_90j":   plan_90j,
    }

# ─────────────────────────────────────────
# NICHES À TRAITER
# ─────────────────────────────────────────

NICHES = [
    "Agences immobilières",
    "Cabinets de comptabilité",
    "Coaches et consultants indépendants",
]

if __name__ == "__main__":
    for niche in NICHES:
        try:
            lancer_pipeline(niche)
        except Exception as e:
            print(f"❌ Erreur sur la niche '{niche}' : {e}")
