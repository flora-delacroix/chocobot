import json, os
import db
import llm

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


def handle_chat(session_id, message):
    db.save_message(session_id, "user", message)
    customer = db.get_customer(session_id)
    print(f"[chat] {customer} : {message}")

    system = SYSTEM_PROMPT + customer_context(customer)
    messages = [{"role": "system", "content": system}] + db.get_history(session_id)

    try:
        reply, usage = llm.chat(llm.BIG_MODEL, messages, max_tokens=1500)
    except Exception:
        reply = "Désolé, une erreur est survenue. Réessayez plus tard."

    db.save_message(session_id, "assistant", reply)
    return {"reply": reply}
