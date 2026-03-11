import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from crewai import Agent, Task, Crew, Process

# ============================================================
# CONFIGURATION
# ============================================================
os.environ["GROQ_API_KEY"] = "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"
os.environ["OPENAI_API_KEY"] = "fake-key"

SUPABASE_URL = "https://molqnxwmnnfwvcjvujgd.supabase.co"
SUPABASE_KEY = "sb_publishable_8gDItFCUvX7X1OwqjWBeXA_vASgp6VC"
MODELE = "groq/llama-3.3-70b-versatile"

GMAIL_EMAIL = "inonbkrs@gmail.com"
GMAIL_PASSWORD = "xdto mcqg mciv snno"

resultats = {}

# ============================================================
# FONCTION — ENVOYER PAR EMAIL
# ============================================================
def envoyer_email(rapport):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_EMAIL
        msg['To'] = GMAIL_EMAIL
        msg['Subject'] = f"🤖 Rapport Business IA — {datetime.now().strftime('%d/%m/%Y à %H:%M')}"

        corps = f"""
Bonjour,

Voici le rapport complet de vos agents IA pour aujourd'hui.

{'='*50}
{rapport}
{'='*50}

Bonne journée !
Vos agents IA 🤖
        """
        msg.attach(MIMEText(corps, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email envoyé avec succès à", GMAIL_EMAIL)
    except Exception as e:
        print(f"❌ Erreur email : {e}")

# ============================================================
# FONCTION — ENVOYER DANS SUPABASE
# ============================================================
def envoyer_rapport_supabase(data):
    url = f"{SUPABASE_URL}/rest/v1/rapports"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        print("✅ Rapport envoyé dans Supabase avec succès !")
    else:
        print(f"❌ Erreur Supabase : {response.status_code} — {response.text}")

# ============================================================
# CALLBACKS
# ============================================================
def callback_analyse(output):
    resultats["analyse"] = str(output.raw) if hasattr(output, 'raw') else str(output)
    print("✅ Analyse capturée !")

def callback_prospection(output):
    resultats["prospects"] = str(output.raw) if hasattr(output, 'raw') else str(output)
    print("✅ Prospects capturés !")

def callback_marketing(output):
    resultats["marketing"] = str(output.raw) if hasattr(output, 'raw') else str(output)
    print("✅ Marketing capturé !")

def callback_ops(output):
    resultats["ops"] = str(output.raw) if hasattr(output, 'raw') else str(output)
    print("✅ Plan ops capturé !")

# ============================================================
# LES 4 AGENTS
# ============================================================
analyste = Agent(
    role="Analyste de Marché Expert",
    goal="Identifier la meilleure niche business pour maximiser les revenus",
    backstory="Expert en analyse de marché avec 15 ans d'expérience.",
    llm=MODELE, verbose=True
)

prospecteur = Agent(
    role="Expert en Prospection Commerciale",
    goal="Trouver 5 prospects de secteurs DIFFÉRENTS (ex: restauration, immobilier, santé, e-commerce, industrie) avec nom, email, téléphone, secteur et budget",
    backstory="Chasseur de clients avec 10 ans d'expérience.",
    llm=MODELE, verbose=True
)

marketeur = Agent(
    role="Expert Marketing et Copywriting",
    goal="Créer des emails de vente complets et percutants",
    backstory="Expert en marketing digital et copywriting.",
    llm=MODELE, verbose=True
)

ops_manager = Agent(
    role="Operations Manager et Stratège Business",
    goal="Créer un plan d'action béton avec des KPIs mesurables",
    backstory="Expert en lancement de startups.",
    llm=MODELE, verbose=True
)

# ============================================================
# LES 4 TÂCHES
# ============================================================
tache_analyse = Task(
    description="""Analyse le marché des services IA pour tous types d'entreprises : startups, PME, grandes entreprises, commerces, restaurants, agences, cabinets, etc.
    Réponds avec ce format EXACT :
    NICHE: [niche choisie]
    REVENUS: [revenus potentiels par mois en euros]
    BUDGET: [budget démarrage]
    CONCURRENTS: [3 concurrents]
    POURQUOI: [raison du choix]""",
    expected_output="Analyse avec NICHE, REVENUS, BUDGET, CONCURRENTS, POURQUOI",
    agent=analyste,
    callback=callback_analyse
)

tache_prospection = Task(
    description="""Crée une liste de 5 prospects idéaux pour vendre des agents IA.
    Format EXACT pour chaque prospect :
    PROSPECT 1:
    - Nom entreprise: [nom]
    - Secteur: [secteur]
    - Problème: [problème principal]
    - Email: [email]
    - Téléphone: [téléphone]
    - Budget: [budget estimé]
    PROSPECT 2: [même format]
    ... jusqu'à PROSPECT 5""",
    expected_output="5 prospects complets avec nom, secteur, email, téléphone, budget",
    agent=prospecteur,
    callback=callback_prospection
)

tache_marketing = Task(
    description="""Crée 2 emails de vente professionnels.
    Format EXACT :
    EMAIL 1 - PREMIER CONTACT:
    Objet: [objet]
    Corps: [email complet]
    ---
    EMAIL 2 - RELANCE:
    Objet: [objet]
    Corps: [email complet]""",
    expected_output="2 emails complets avec objet et corps",
    agent=marketeur,
    callback=callback_marketing
)

tache_ops = Task(
    description="""Crée le plan 90 jours et les KPIs.
    Format EXACT :
    PLAN 30 JOURS: [liste des actions mois 1]
    PLAN 60 JOURS: [liste des actions mois 2]
    PLAN 90 JOURS: [liste des actions mois 3]
    KPIS:
    - Revenu cible mois 1: [montant]
    - Revenu cible mois 3: [montant]
    - Nombre clients cible: [nombre]
    - Taux conversion cible: [pourcentage]""",
    expected_output="Plan 90 jours + KPIs structurés",
    agent=ops_manager,
    callback=callback_ops
)

# ============================================================
# LANCEMENT DES AGENTS
# ============================================================
print("🚀 Lancement des agents IA...")
print("=" * 50)

crew = Crew(
    agents=[analyste, prospecteur, marketeur, ops_manager],
    tasks=[tache_analyse, tache_prospection, tache_marketing, tache_ops],
    process=Process.sequential,
    verbose=True
)

crew.kickoff()

# ============================================================
# EXTRACTION ET ENVOI
# ============================================================
analyse = resultats.get("analyse", "")
prospects = resultats.get("prospects", "")
marketing = resultats.get("marketing", "")
ops = resultats.get("ops", "")

niche = ""
revenus = ""
for ligne in analyse.split("\n"):
    if ligne.strip().startswith("NICHE:"):
        niche = ligne.replace("NICHE:", "").strip()
    if ligne.strip().startswith("REVENUS:"):
        revenus = ligne.replace("REVENUS:", "").strip()

rapport_final = f"""
{'='*60}
RAPPORT BUSINESS IA — {datetime.now().strftime('%d/%m/%Y à %H:%M')}
{'='*60}

== ANALYSE DE MARCHÉ ==
{analyse}

== PROSPECTS ==
{prospects}

== MARKETING ==
{marketing}

== PLAN 90 JOURS & KPIs ==
{ops}
{'='*60}
"""

# Sauvegarder en local
with open("rapport_business.txt", "w", encoding="utf-8") as f:
    f.write(rapport_final)
print("\n✅ Rapport sauvegardé : rapport_business.txt")

# Envoyer dans Supabase
print("\n📤 Envoi dans Supabase...")
envoyer_rapport_supabase({
    "contenu": rapport_final,
    "niche": niche,
    "revenus_estimes": revenus,
    "prospects": prospects,
    "emails_vente": marketing,
    "plan_90_jours": ops,
    "kpis": ops,
    "date_creation": datetime.utcnow().isoformat()
})

# Envoyer par email
print("\n📧 Envoi par email...")
envoyer_email(rapport_final)

print("\n🎉 Tout est terminé !")
