import json, os
import db
import llm
import re

with open(os.path.join(os.path.dirname(__file__), "data", "catalog.json"), encoding="utf-8") as f:
    CATALOG = json.load(f)

SYSTEM_PROMPT = """Tu es ChocoBot, un assistant virtuel automatisé par intelligence artificielle pour la Maison Delcourt, chocolatier artisanal à Lille.

RÔLE ET PERIMÈTRE STRICT :
1. Tu es une IA d'aide à la vente. Si l'utilisateur te demande si tu es une vraie personne ou un chocolatier humain, tu dois explicitement répondre que tu es un système d'IA automatisé.
2. Tu réponds UNIQUEMENT aux questions directement liées à la Maison Delcourt : nos chocolats, nos coffrets, nos tarifs, la livraison, les horaires de la boutique et la gestion des allergies.
3. Tu dois IMPÉRATIVEMENT refuser de traiter toute question hors-sujet (politique, actualités, culture générale, conversations personnelles comme "ça va ?", etc.). 

CONSIGNES DE REFUS ET RECADRAGE :
- Pour tout message hors-sujet, ne tente PAS d'y répondre ni d'épiloguer. Réponds immédiatement par une phrase courte de recadrage : « Je suis un assistant virtuel dédié exclusivement à la Maison Delcourt. Je ne peux vous aider que pour le choix de vos chocolats, nos horaires ou nos services. Comment puis-je vous aider ? »

CONSIGNES RELATIVES AU CATALOGUE ET AUX ALLERGIES :
- Ne propose QUE des coffrets figurant dans le catalogue ci-dessous. N'invente AUCUN produit, aucun ingrédient ni aucun prix.
- Si le client mentionne une allergie ou une intolérance, vérifie strictement la composition des produits. En cas de doute, recommande de consulter la fiche produit officielle.
- Ne cherche jamais à deviner ou analyser l'état d'esprit, l'humeur ou les émotions du client.

CATALOGUE OFFICIEL :
""" + json.dumps(CATALOG, ensure_ascii=False)


def customer_context(customer):
    """Décrit au LLM ce que le client a enregistré dans le formulaire."""
    if not any(customer.get(k) for k in ["name", "email", "allergies", "children_ages"]):
        return "\n\nInformations enregistrées sur le client : aucune."
    lines = ["\n\nInformations enregistrées sur le client (saisies par lui dans le formulaire) :"]
    if customer.get("name"):
        lines.append(f"- Nom : {customer['name']}")
    if customer.get("email"):
        lines.append(f"- Email : {customer['email']}")
    if customer.get("allergies"):
        lines.append(f"- Allergies : {customer['allergies']}")
    if customer.get("children_ages"):
        lines.append(f"- Âge des enfants : {customer['children_ages']}")
    lines.append("Appelle le client par son prénom, tiens compte de ces informations et réponds à toute question le concernant.")
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


def handle_chat(session_id, message):
    db.save_message(session_id, "user", message)
    customer = db.get_customer(session_id)
    print(f"[chat] {customer} : {message}")

    response_faq = get_predifined_response(message)
    if response_faq:
        db.save_message(session_id, "assistant", response_faq)
        
        return {
            "reply": response_faq,
            "prompt_eval_count": 0,
            "eval_count": 0,
            "eval_duration": 0,
            "from_cache": True
        }

    system = SYSTEM_PROMPT + customer_context(customer)
    messages = [{"role": "system", "content": system}] + db.get_history(session_id)

    try:
        reply, usage = llm.chat(llm.BIG_MODEL, messages, max_tokens=1500)
    except Exception:
        reply = "Désolé, une erreur est survenue. Réessayez plus tard."

    db.save_message(session_id, "assistant", reply)
    return {"reply": reply}