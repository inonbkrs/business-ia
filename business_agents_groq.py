import os
import re
import sys
import json
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
from supabase import create_client

# Google Sheets (optionnel — dégradé si non configuré)
try:
    import gspread
    from google.oauth2.service_account import Credentials as GoogleCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY")
SUPABASE_URL   = os.environ.get("SUPABASE_URL")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY")
GMAIL_USER     = os.environ.get("GMAIL_USER", "inonbkrs@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
GROQ_MODEL     = "llama-3.3-70b-versatile"

# Google Sheets
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")  # JSON string du compte de service
GOOGLE_SHEET_ID    = os.environ.get("GOOGLE_SHEET_ID", "")  # ID du Google Sheet
SHEET_HEADERS = ["Prénom", "Entreprise", "Email", "Niche", "Date envoi", "Statut", "J1", "J3", "J5", "J7"]

# ⚠️ MODE TEST : tous les emails arrivent dans ta Gmail
# Mets False quand tu as de vrais prospects
MODE_TEST = True

# 📊 LIMITES ANTI-SPAM
MAX_PROSPECTS_PAR_NICHE = 3   # 3 emails par jour max
NICHES = [
    "Agences immobilières",
    "Cabinets de comptabilité",
    "Coaches et consultants indépendants",
]

groq_client     = Groq(api_key=GROQ_API_KEY)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────
# SÉLECTION DE LA NICHE DU JOUR
# Rotation automatique : lundi=niche1, mardi=niche2, etc.
# ─────────────────────────────────────────
def get_niche_du_jour() -> str:
    jour = datetime.datetime.utcnow().weekday()  # 0=lundi, 1=mardi...
    index = jour % len(NICHES)
    niche = NICHES[index]
    print(f"📅 Niche du jour (jour {jour}) : {niche}")
    return niche

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
# GOOGLE SHEETS — CLIENT & UTILITAIRES
# ─────────────────────────────────────────
def get_sheets_client():
    """Initialise le client gspread avec le compte de service Google."""
    if not GSPREAD_AVAILABLE:
        print("⚠️  gspread non installé — Google Sheets ignoré")
        return None
    if not GOOGLE_CREDENTIALS:
        print("⚠️  GOOGLE_CREDENTIALS non configuré — Google Sheets ignoré")
        return None
    try:
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = GoogleCredentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(credentials)
    except Exception as e:
        print(f"⚠️  Erreur connexion Google Sheets : {e}")
        return None

def get_sheet():
    """Ouvre la feuille Google Sheets par ID et initialise les en-têtes si vide."""
    gc = get_sheets_client()
    if not gc:
        return None
    if not GOOGLE_SHEET_ID:
        print("⚠️  GOOGLE_SHEET_ID non configuré — Google Sheets ignoré")
        return None
    try:
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.sheet1
        # Initialise les en-têtes si la première ligne est vide
        existing = worksheet.row_values(1)
        if not existing or existing[0] != "Prénom":
            worksheet.insert_row(SHEET_HEADERS, 1)
            print("📊 En-têtes Google Sheets initialisés")
        return worksheet
    except Exception as e:
        print(f"⚠️  Erreur accès Google Sheet : {e}")
        return None

def ajouter_prospect_sheet(worksheet, prospect: dict, niche: str, date_envoi: str):
    """Ajoute un prospect dans le Google Sheet après envoi de l'email initial."""
    if not worksheet:
        return
    try:
        row = [
            prospect.get("prenom", ""),
            prospect.get("entreprise", ""),
            prospect.get("email", ""),
            niche,
            date_envoi,
            "Envoyé",
            "",  # J1
            "",  # J3
            "",  # J5
            "",  # J7
        ]
        worksheet.append_row(row)
        print(f"   📊 Sheet : {prospect.get('prenom')} — {prospect.get('entreprise')} ajouté")
    except Exception as e:
        print(f"   ⚠️  Erreur ajout Sheet : {e}")

# ─────────────────────────────────────────
# AGENTS DE BASE
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

Génère exactement {MAX_PROSPECTS_PAR_NICHE} profils de prospects idéaux.
IMPORTANT : Réponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ou après.
Format exact :
[
  {{
    "entreprise": "Nom de l'entreprise",
    "secteur": "Secteur précis",
    "probleme": "Problème principal",
    "budget": "Budget estimé",
    "email": "prenom.nom@entreprise.fr",
    "prenom": "Prénom du contact",
    "nom": "Nom du contact"
  }}
]
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
# ─────────────────────────────────────────
def agent_defaillance(niche: str, rapport: dict) -> dict:
    prompt = f"""
Tu es un agent de contrôle qualité pour un système business automatisé.
Niche analysée : {niche}

Rapport généré :
- Analyse marché : {rapport.get('analyse', '')[:400]}
- Prospects : {rapport.get('prospects', '')[:300]}
- Email de vente : {rapport.get('email', '')[:300]}
- Plan 90 jours : {rapport.get('plan_90j', '')[:300]}

Évalue et détecte les défaillances :
1. Score de santé global (0 à 100)
2. Problèmes détectés
3. Niveau d'alerte : VERT / ORANGE / ROUGE
4. Actions correctives

Réponds en français, structuré et concis.
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
        contexte_historique = f"{nb_rapports} rapport(s) précédent(s) trouvé(s)."
    except Exception:
        contexte_historique = "Pas d'historique disponible."

    prompt = f"""
Tu es un agent d'évolution et d'optimisation business.
Niche : {niche} | Historique : {contexte_historique}

Rapport actuel :
- Analyse : {rapport_actuel.get('analyse', '')[:400]}
- Email vente : {rapport_actuel.get('email', '')[:300]}

Propose :
1. 3 axes d'amélioration concrets
2. Nouvelles niches connexes à explorer
3. Stratégie pour augmenter les revenus
4. Message de motivation pour l'entrepreneur

Réponds en français, structuré et actionnable.
"""
    return groq_llm(prompt)

# ─────────────────────────────────────────
# AGENT 7 — ENVOI EMAILS AUX PROSPECTS 📧
# ─────────────────────────────────────────
def extraire_prospects(prospects_json: str) -> list:
    try:
        match = re.search(r'\[.*\]', prospects_json, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"⚠️  Impossible de parser les prospects JSON : {e}")
    return []

def agent_envoi_prospects(niche: str, prospects_json: str, email_vente_template: str, worksheet=None):
    if not GMAIL_PASSWORD:
        print("⚠️  GMAIL_PASSWORD non configuré — envoi ignoré")
        return

    prospects = extraire_prospects(prospects_json)[:MAX_PROSPECTS_PAR_NICHE]

    if not prospects:
        print("⚠️  Aucun prospect extrait — envoi ignoré")
        return

    print(f"📧 Envoi à {len(prospects)} prospect(s) pour : {niche}")
    today_str = datetime.date.today().isoformat()

    for i, prospect in enumerate(prospects, 1):
        prenom     = prospect.get("prenom", "")
        entreprise = prospect.get("entreprise", "")
        probleme   = prospect.get("probleme", "")
        email_dest = prospect.get("email", "")

        if not email_dest:
            continue

        # Email personnalisé pour ce prospect
        prompt_perso = f"""
Personnalise cet email de vente pour ce prospect :
Prénom : {prenom} | Entreprise : {entreprise} | Problème : {probleme} | Niche : {niche}

Template :
{email_vente_template}

Réécris l'email en intégrant naturellement le prénom, l'entreprise et le problème.
150 mots max. Réponds UNIQUEMENT avec l'email (objet + corps).
"""
        email_perso = groq_llm(prompt_perso)

        lignes = email_perso.strip().split('\n')
        objet = f"Une solution IA pour {entreprise}"
        corps = email_perso

        for ligne in lignes[:3]:
            if "objet" in ligne.lower() or ligne.startswith("Objet"):
                objet = ligne.split(":", 1)[-1].strip()
                corps = "\n".join(lignes[1:]).strip()
                break

        destinataire = GMAIL_USER if MODE_TEST else email_dest

        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = destinataire
        msg["Subject"] = f"[TEST → {email_dest}] {objet}" if MODE_TEST else objet
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(GMAIL_USER, GMAIL_PASSWORD)
                server.sendmail(GMAIL_USER, destinataire, msg.as_string())
            print(f"   ✅ [{i}/{len(prospects)}] → {email_dest} ({entreprise})")
            # Enregistrement dans Google Sheets
            ajouter_prospect_sheet(worksheet, prospect, niche, today_str)
        except Exception as e:
            print(f"   ❌ [{i}/{len(prospects)}] Erreur {email_dest} : {e}")

# ─────────────────────────────────────────
# RELANCES AUTOMATIQUES J1 / J3 / J5 / J7
# ─────────────────────────────────────────
def generer_email_relance(prospect_data: dict, jour: int) -> tuple:
    """Génère un email de relance personnalisé pour le jour J+n."""
    prenom     = prospect_data.get("prenom", "")
    entreprise = prospect_data.get("entreprise", "")
    niche      = prospect_data.get("niche", "")

    types_relance = {
        1: "suivi court et bienveillant — 1 ou 2 phrases + question ouverte simple",
        3: "apport de valeur — partage une statistique ou insight utile pour leur secteur",
        5: "dernière tentative sérieuse — urgence douce, sans pression, montre que tu comprends leur problème",
        7: "clôture propre et professionnelle — dit que c'est le dernier email, laisse la porte ouverte",
    }
    type_relance = types_relance.get(jour, "suivi")

    prompt = f"""
Tu es un expert en cold email B2B. Écris un email de relance J+{jour} pour ce prospect.
Type de relance : {type_relance}

Prospect :
- Prénom : {prenom}
- Entreprise : {entreprise}
- Secteur : {niche}

Règles absolues :
- Maximum 80 mots dans le corps
- Première ligne = "Objet: [ton objet ici]"
- Ton professionnel, chaleureux, jamais insistant
- En français uniquement
- Pour J+7 seulement : précise que c'est le dernier message
"""
    response = groq_llm(prompt)
    lignes = response.strip().split('\n')
    objet = f"Re: Nexivo — {entreprise}"
    corps = response

    for ligne in lignes[:3]:
        if "objet" in ligne.lower():
            objet = ligne.split(":", 1)[-1].strip()
            corps = "\n".join(lignes[1:]).strip()
            break

    return objet, corps

def traiter_relances():
    """Vérifie le Google Sheet et envoie les relances dues (J1/J3/J5/J7)."""
    worksheet = get_sheet()
    if not worksheet:
        print("⚠️  Relances ignorées — Google Sheets non configuré")
        return

    if not GMAIL_PASSWORD:
        print("⚠️  Relances ignorées — GMAIL_PASSWORD non configuré")
        return

    today = datetime.date.today()
    all_rows = worksheet.get_all_records()

    if not all_rows:
        print("📊 Aucun prospect dans le Sheet — rien à relancer")
        return

    print(f"📊 Vérification de {len(all_rows)} prospect(s) pour relances...")
    relances_envoyees = 0

    # Mapping colonne → index (1-based) dans le sheet
    col_index_map = {
        "J1": SHEET_HEADERS.index("J1") + 1,
        "J3": SHEET_HEADERS.index("J3") + 1,
        "J5": SHEET_HEADERS.index("J5") + 1,
        "J7": SHEET_HEADERS.index("J7") + 1,
    }

    for idx, row in enumerate(all_rows, 2):  # Ligne 2 = première ligne de données
        date_envoi_str = row.get("Date envoi", "")
        if not date_envoi_str:
            continue

        try:
            date_envoi = datetime.date.fromisoformat(str(date_envoi_str))
        except ValueError:
            continue

        delta = (today - date_envoi).days

        prospect_data = {
            "prenom":     row.get("Prénom", ""),
            "entreprise": row.get("Entreprise", ""),
            "email":      row.get("Email", ""),
            "niche":      row.get("Niche", ""),
        }

        for jour, col in [(1, "J1"), (3, "J3"), (5, "J5"), (7, "J7")]:
            if delta == jour and not row.get(col):
                prenom     = prospect_data["prenom"]
                entreprise = prospect_data["entreprise"]
                email_dest = prospect_data["email"]

                if not email_dest:
                    continue

                print(f"   📬 Relance J+{jour} → {prenom} ({entreprise})")
                objet, corps = generer_email_relance(prospect_data, jour)

                destinataire = GMAIL_USER if MODE_TEST else email_dest

                msg = MIMEMultipart()
                msg["From"]    = GMAIL_USER
                msg["To"]      = destinataire
                msg["Subject"] = f"[TEST → {email_dest}] {objet}" if MODE_TEST else objet
                msg.attach(MIMEText(corps, "plain", "utf-8"))

                try:
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                        server.login(GMAIL_USER, GMAIL_PASSWORD)
                        server.sendmail(GMAIL_USER, destinataire, msg.as_string())
                    # Marquer la relance comme envoyée dans le Sheet
                    worksheet.update_cell(idx, col_index_map[col], f"Envoyé {today.isoformat()}")
                    print(f"      ✅ Relance J+{jour} envoyée et marquée dans le Sheet")
                    relances_envoyees += 1
                except Exception as e:
                    print(f"      ❌ Erreur relance J+{jour} : {e}")

    print(f"✅ Relances terminées : {relances_envoyees} email(s) envoyé(s)")

# ─────────────────────────────────────────
# ENVOI RAPPORT COMPLET
# ─────────────────────────────────────────
def envoyer_email_rapport(niche, rapport, defaillance, evolution):
    if not GMAIL_PASSWORD:
        return

    niveau = defaillance.get("niveau_alerte", "VERT")
    emoji  = {"VERT": "✅", "ORANGE": "⚠️", "ROUGE": "🚨"}.get(niveau, "✅")

    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER
    msg["Subject"] = f"{emoji} Rapport IA — {niche} | {datetime.date.today()} | {niveau}"
    corps = f"""
╔══════════════════════════════════════╗
   RAPPORT BUSINESS IA — {niche}
   Date : {datetime.date.today()}
╚══════════════════════════════════════╝

📊 ANALYSE MARCHÉ
{rapport.get('analyse', '')}

👥 PROSPECTS ({MAX_PROSPECTS_PAR_NICHE} contacts)
{rapport.get('prospects', '')}

📧 EMAIL DE VENTE (template)
{rapport.get('email', '')}

📅 PLAN 90 JOURS
{rapport.get('plan_90j', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 AGENT DÉFAILLANCE — {niveau}
{defaillance.get('analyse', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 AGENT ÉVOLUTION
{evolution}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Business IA System — {datetime.date.today()}
"""
    msg.attach(MIMEText(corps, "plain", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        print(f"✅ Rapport envoyé — Alerte : {niveau}")
    except Exception as e:
        print(f"❌ Erreur rapport : {e}")

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
    print(f"✅ Supabase — ID: {result.data[0]['id'] if result.data else 'N/A'}")

# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────
def lancer_pipeline(niche: str):
    print(f"\n🚀 Pipeline : {niche}")
    print("─" * 50)

    # Initialiser Google Sheets en amont (dégradé si non configuré)
    worksheet = get_sheet()

    print("🔍 Agent 1 — Analyse marché...")
    analyse = agent_analyse_marche(niche)

    print("👥 Agent 2 — Génération prospects...")
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

    print("🚨 Agent 5 — Défaillances...")
    defaillance = agent_defaillance(niche, rapport)
    print(f"   → Alerte : {defaillance['niveau_alerte']}")

    print("📈 Agent 6 — Évolution...")
    evolution = agent_evolution(niche, rapport)

    print(f"📬 Agent 7 — Envoi aux {MAX_PROSPECTS_PAR_NICHE} prospects...")
    agent_envoi_prospects(niche, prospects, email_vente, worksheet=worksheet)

    print("💾 Sauvegarde Supabase...")
    sauvegarder_rapport(niche, rapport, defaillance, evolution)

    print("📨 Rapport complet...")
    envoyer_email_rapport(niche, rapport, defaillance, evolution)

    print(f"✅ Terminé : {niche}\n")

# ─────────────────────────────────────────
# LANCEMENT — 1 NICHE PAR JOUR + RELANCES
# ─────────────────────────────────────────
if __name__ == "__main__":
    mode = "TEST" if MODE_TEST else "PRODUCTION"
    print(f"\n{'='*50}")
    print(f"  BUSINESS IA SYSTEM — Mode : {mode}")
    print(f"  {datetime.date.today()} — 3 emails max aujourd'hui")
    print(f"{'='*50}")

    # Mode relances uniquement (pour tests ou CI séparé)
    if len(sys.argv) > 1 and sys.argv[1] == "relances":
        print("\n📬 Mode RELANCES uniquement")
        traiter_relances()
        sys.exit(0)

    # Pipeline principal
    niche_du_jour = get_niche_du_jour()
    try:
        lancer_pipeline(niche_du_jour)
    except Exception as e:
        print(f"❌ Erreur pipeline : {e}")

    # Relances automatiques en fin de pipeline
    print(f"\n{'─'*50}")
    print("📬 Vérification des relances J1/J3/J5/J7...")
    try:
        traiter_relances()
    except Exception as e:
        print(f"⚠️  Erreur relances : {e}")
