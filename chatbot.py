import json, os
import db, llm, re
import logging, sentry_sdk

with open(os.path.join(os.path.dirname(__file__), "data", "catalog.json"), encoding="utf-8") as f:
    CATALOG = json.load(f)

SYSTEM_PROMPT = """Tu es ChocoBot, un assistant virtuel automatisé par intelligence artificielle pour la Maison Delcourt, chocolatier artisanal à Lille.

RÔLE ET PERIMÈTRE STRICT :
1. Tu es une IA d'aide à la vente. Si l'utilisateur te demande si tu es une vraie personne ou un chocolatier humain, tu dois explicitement répondre que tu es un système d'IA automatisé.
2. Tu réponds UNIQUEMENT aux questions directement liées à la Maison Delcourt : nos chocolats, nos coffrets, nos tarifs, la livraison, les horaires de la boutique et la gestion des allergies.
3. Tu dois IMPÉRATIVEMENT refuser de traiter toute question hors-sujet (politique, actualités, culture générale, conversations personnelles comme "ça va ?", etc.). 

INTERPRÉTATION DU CONTEXTE CLIENT (IMPLICITE ET CIBLES) :
- Toute recherche par budget (ex : "un coffret à 30 euros"), par destinataire (ex : "un cadeau pour des enfants", "pour ma mère") ou par occasion est STRICTEMENT DANS LE PÉRIMÈTRE.
- Pour ces demandes, NE GÉNÈRE JAMAIS la phrase de recadrage/refus. Réponds directement avec les coffrets adaptés du catalogue.
- Lorsqu'un montant est mentionné (ex: "un coffret à 30 euros"), sélectionne en priorité les coffrets dont le prix est inférieur ou égal à ce montant (prix ≤ montant). Si aucun produit ne correspond exactement, tu peux proposer un coffret dépassant le budget de 5 € maximum (prix ≤ budget + 5 €). Exclus strictement tout produit dépassant cette marge de 5 €.

CONSIGNES DE REFUS ET RECADRAGE :
- Utilise la phrase de recadrage UNIQUEMENT pour les sujets totalement étrangers aux chocolats et à la boutique (météo, politique, devoirs, conversations personnelles hors-sujet, etc.) :
« Je suis un assistant virtuel dédié exclusivement à la Maison Delcourt. Je ne peux vous aider que pour le choix de vos chocolats, nos horaires ou nos services. Comment puis-je vous renseigner ? »

CONSIGNES RELATIVES AU CATALOGUE ET AUX ALLERGIES :
- Ne propose QUE des coffrets figurant dans le catalogue ci-dessous. N'invente AUCUN produit, aucun ingrédient ni aucun prix.
- Si le client mentionne une allergie ou une intolérance, vérifie strictement la composition des produits. En cas de doute, recommande de consulter la fiche produit officielle.
- Ne cherche jamais à deviner ou analyser l'état d'esprit, l'humeur ou les émotions du client.

FORMAT ET CONCISION (SOBRIÉTÉ NUMÉRIQUE) :
- Sois direct, clair et va à l'essentiel.
- Limite tes réponses à 2 ou 3 phrases maximum par message, ou à une liste à puces très courte de 2 à 3 propositions maximum.
- Évite les formules de politesse à rallonge, les préambules inutiles et le bavardage marketing excessif.
- Présente chaque coffret de manière synthétique : Nom du coffret, Prix (€), et la raison principale du choix.

CATALOGUE OFFICIEL :
""" + json.dumps(CATALOG, ensure_ascii=False)


def customer_context(email):
    """Décrit au LLM ce que le client a enregistré."""
    if not email:
        return "\n\nAucun utilisateur connecté."

    user = db.get_user(email)
    if not user or not any(user.get(k) for k in ["allergies_encrypted", "tranche_age"]):
        return "\n\nAucune information enregistrée sur le client."

    lines = ["\n\nInformations enregistrées sur le client :"]
    if user.get("allergies_encrypted"):
        lines.append(f"- Allergies : {user['allergies_encrypted']}")
    if user.get("tranche_age"):
        lines.append(f"- Tranche d'âge : {user['tranche_age']}")
    lines.append("Tiens compte de ces informations et réponds à toute question le concernant.")
    return "\n".join(lines)


PREDEFINED_FAQ = {
    "horaires": {
        "keywords": [r"\bhoraire", r"\bhoraires", r"ouvert", r"ouverte", r"ouverts", r"ouvrez", r"ouverture", r"fermeture", r"fermez", r"fermé", r"fermés", r"fermée", r"\bheure\b"],
        "response": "La Maison Delcourt est ouverte du lundi au samedi de 10h à 18h, et le dimanche de 11h à 17h."
    },
    "adresse_boutique": {
        "keywords": [r"adresse", r"où êtes-vous", r"ou etes vous", r"magasin", r"boutique", r"situé", r"situés", r"où se trouve", r"ou se trouve"],
        "response": "Notre chocolaterie est située au cœur du Vieux Lille, au 12 Rue Esquermoise."
    },
    "livraison": {
        "keywords": [r"livraison", r"livrer", r"expédition", r"frais de port", r"colis", r"recevoir"],
        "response": "Nous proposons des livraisons dans toute la métropole lilloise. Vous pouvez choisir la date et l'heure de livraison lors de votre commande en ligne."
    },
    "contact": {
        "keywords": [r"téléphone", r"telephone", r"mail", r"email", r"contact", r"joindre", r"appeler"],
        "response": "Vous pouvez nous contacter par téléphone au 03 20 00 00 00 (de 10h à 18h du lundi au samedi ou de 11h à 17h le dimanche) ou par e-mail à l'adresse contact@chocolaterie-delcourt.fr."
    }
}

def get_predifined_response(message_client: str) -> str | None:
    """Analyse le message client et renvoie une réponse prédéfinie si une question simple/récurrente est détectée, évitant ainsi un appel coûteux au LLM."""
    if not message_client:
        return None

    msg_normalise = message_client.lower().strip()

    for intent, data in PREDEFINED_FAQ.items():
        for pattern in data["keywords"]:
            if re.search(pattern, msg_normalise):
                return data["response"]

    return None


def is_simple_query(message: str) -> bool:
    """
    Détermine si une requête est suffisamment simple pour le modèle léger (1B).
    Si le message contient une demande de conseil, de produit ou de personnalisation, on renvoie False pour utiliser le grand modèle (3B).
    """
    msg = message.lower().strip()
    words = msg.split()

    complex_keywords = [
        "conseil", "recommande", "suggère", "suggestion", "choisir", "offrir", "cadeau", "cherche",
        "chocolat", "noir", "lait", "blanc", "praliné", "noisette", "noix", "coffret",
        "composition", "ingrédient", "allergène", "sucre", "bio"
    ]

    if any(keyword in msg for keyword in complex_keywords):
        return False

    if len(words) > 8:
        return False

    return True


def handle_chat(email, message):
    print(f"[chat] {email} : {message}")

    response_faq = get_predifined_response(message)
    if response_faq:
        return {
            "reply": response_faq,
            "prompt_eval_count": 0,
            "eval_count": 0,
            "eval_duration": 0,
            "from_cache": True
        }

    system = SYSTEM_PROMPT + customer_context(email)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": message}]

    selected_model = llm.SMALL_MODEL if is_simple_query(message) else llm.BIG_MODEL

    try:
        reply, usage = llm.chat(selected_model, messages, max_tokens=250)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logging.error(f"[Email {email}] Erreur LLM : {e}")
        reply = "Désolé, notre assistant est temporairement indisponible. Contactez-nous par téléphone ou réessayez plus tard."

    return {"reply": reply}