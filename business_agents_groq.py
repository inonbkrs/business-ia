import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
from supabase import create_client

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")
SUPABASE_URL   = os.environ.get("SUPABASE_URL")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY")
GMAIL_USER     = os.environ.get("GMAIL_USER", "inonbkrs@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
GROQ_MODEL     = "llama-3.3-70b-versatile"

groq_client     = Groq(api_key=GROQ_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────
# FONCTION LLM
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
# AGENTS DE BASE (4 agents originaux)
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
# AGENT 5 — DÉFAILLANCE 🚨
# Détecte les problèmes et envoie une alerte
# ─────────────────────────────────────────
def agent_defaillance(niche: str, rapport: dict) -> dict:
    prompt = f"""
Tu es un agent de contrôle qualité pour un système business automatisé.
Niche analysée : {niche}

Voici le rapport généré :
- Analyse marché : {rapport.get('analyse', '')[:400]}
- Prospects générés : {rapport.get('prospects', '')[:300]}
- Email de vente : {rapport.get('email', '')[:300]}
- Plan 90 jours : {rapport.get('plan_90j', '')[:300]}

Évalue ce rapport et détecte les défaillances potentielles :
1. Score de santé global (0 à 100)
2. Liste des problèmes détectés (vague, incomplet, irréaliste, etc.)
3. Niveau d'alerte : VERT (tout va bien) / ORANGE (attention) / ROUGE (action requise)
4. Actions correctives recommandées

Réponds en français, de façon structurée et concise.
"""
    analyse_defaillance = groq_llm(prompt)

    alerte = "VERT"
    if "ROUGE" in analyse_defaillance.upper():
        alerte = "ROUGE"
    elif "ORANGE" in analyse_defaillance.upper():
        alerte = "ORANGE"

    return {
        "analyse": analyse_defaillance,
        "niveau_alerte": alerte,
        "niche": niche,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# ─────────────────────────────────────────
# AGENT 6 — ÉVOLUTION 📈
# Analyse l'historique et propose des améliorations
# ─────────────────────────────────────────
def agent_evolution(niche: str, rapport_actuel: dict) -> str:
    try:
        historique = supabase_client.table("rapports") \
            .select("contenu, date_creation, kpis") \
            .eq("niche", niche) \
            .order("date_creation", desc=True) \
            .limit(5) \
            .execute()
        nb_rapports = len(historique.data) if historique.data else 0
        contexte_historique = f"{nb_rapports} rapport(s) précédent(s) trouvé(s) pour cette niche."
    except Exception:
        contexte_historique = "Pas d'historique disponible (premier rapport)."

    prompt = f"""
Tu es un agent d'évolution et d'optimisation business.
Niche : {niche}
Historique : {contexte_historique}

Rapport actuel :
- Analyse : {rapport_actuel.get('analyse', '')[:400]}
- Email vente : {rapport_actuel.get('email', '')[:300]}

Propose :
1. 3 axes d'amélioration concrets pour le prochain rapport
2. De nouvelles niches connexes à explorer
3. Une stratégie pour augmenter les revenus estimés
4. Un message de motivation pour l'entrepreneur (court, impactant)

Réponds en français, de façon structurée et actionnable.
"""
    return groq_llm(prompt)

# ─────────────────────────────────────────
# ENVOI EMAIL — RAPPORT COMPLET
# ─────────────────────────────────────────
def envoyer_email_rapport(niche, rapport, defaillance, evolution):
    if not GMAIL_PASSWORD:
        print("⚠️  GMAIL_PASSWORD non configuré — email ignoré")
        return

    niveau = defaillance.get("niveau_alerte", "VERT")
    emoji_alerte = {"VERT": "✅", "ORANGE": "⚠️", "ROUGE": "🚨"}.get(niveau, "✅")

    sujet = f"{emoji_alerte} Rapport IA — {niche} | {datetime.date.today()} | Alerte : {niveau}"
    corps = f"""
╔══════════════════════════════════════╗
   RAPPORT BUSINESS IA AUTOMATISÉ
   Niche : {niche}
   Date  : {datetime.date.today()}
╚══════════════════════════════════════╝

📊 ANALYSE MARCHÉ
{rapport.get('analyse', '')}

👥 PROSPECTS GÉNÉRÉS
{rapport.get('prospects', '')}

📧 EMAIL DE VENTE
{rapport.get('email', '')}

📅 PLAN 90 JOURS
{rapport.get('plan_90j', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 AGENT DÉFAILLANCE — Niveau : {niveau}
{defaillance.get('analyse', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 AGENT ÉVOLUTION — Recommandations
{evolution}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Généré automatiquement par Business IA System
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
        print(f"✅ Email envoyé — Alerte : {niveau}")
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")

# ─────────────────────────────────────────
# SAUVEGARDE SUPABASE
# ─────────────────────────────────────────
def sauvegarder_rapport(niche, rapport, defaillance, evolution):
    data = {
        "niche":           niche,
        "contenu":         rapport.get("analyse", ""),
        "revenus_estimes": "5 000 – 15 000 € / mois",
        "prospects":       rapport.get("prospects", ""),
        "emails_vente":    rapport.get("email", ""),
        "plan_90_jours":   rapport.get("plan_90j", ""),
        "kpis":            f"Alerte: {defaillance.get('niveau_alerte','VERT')} | {evolution[:200]}",
        "date_creation":   datetime.datetime.utcnow().isoformat(),
    }
    result = supabase_client.table("rapports").insert(data).execute()
    print(f"✅ Sauvegardé dans Supabase — ID: {result.data[0]['id'] if result.data else 'N/A'}")

# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────
def lancer_pipeline(niche: str):
    print(f"\n🚀 Pipeline lancé pour : {niche}")
    print("─" * 50)

    print("🔍 Agent 1 — Analyse de marché...")
    analyse = agent_analyse_marche(niche)

    print("👥 Agent 2 — Génération de prospects...")
    prospects = agent_generation_prospects(niche, analyse)

    print("📧 Agent 3 — Email de vente...")
    email_vente = agent_email_vente(niche, analyse)

    print("📅 Agent 4 — Plan 90 jours...")
    plan_90j = agent_plan_90_jours(niche)

    rapport = {
        "analyse":   analyse,
        "prospects": prospects,
        "email":     email_vente,
        "plan_90j":  plan_90j,
    }

    print("🚨 Agent 5 — Détection défaillances...")
    defaillance = agent_defaillance(niche, rapport)
    print(f"   → Niveau alerte : {defaillance['niveau_alerte']}")

    print("📈 Agent 6 — Analyse évolution...")
    evolution = agent_evolution(niche, rapport)

    print("💾 Sauvegarde Supabase...")
    sauvegarder_rapport(niche, rapport, defaillance, evolution)

    print("📬 Envoi email rapport complet...")
    envoyer_email_rapport(niche, rapport, defaillance, evolution)

    print(f"✅ Pipeline terminé pour : {niche}\n")

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
            print(f"❌ Erreur sur '{niche}' : {e}")
