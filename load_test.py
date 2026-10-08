"""Envoie une série de messages réalistes à ChocoBot (serveur lancé sur le port 8000).
Usage : python load_test.py [nombre_de_conversations] (défaut : 2, soit 10 messages)
Mesure les tokens, le coût estimé en production cloud et l'empreinte carbone.
"""
import json, sys, time, urllib.request

BASE = "http://localhost:8000"
SCENARIO = [
    "Quels sont vos horaires ?",
    "Je cherche un coffret pour 30 euros, mon fils est allergique aux noisettes.",
    "Et pour les enfants, vous avez quoi ?",
    "Quels sont vos horaires ?",
    "Merci, je prends le coffret sans noix !",
]

# --- TARIFS ET FACTEURS D'IMPACT (PROD / CLOUD) ---
# Tarifs type API Cloud (ex: Mistral Small / GPT-3.5 Turbo)
TARIF_IN_PER_1K = 0.0015   # € pour 1000 tokens en entrée
TARIF_OUT_PER_1K = 0.0020  # € pour 1000 tokens en sortie

# Empreinte carbone Cloud moyenne (Facteur d'émission ~0.2g CO2e pour 1k tokens)
CARBONE_PER_1K_TOKENS = 0.2 # gCO2e par tranche de 1000 tokens (Inference Cloud)

def estimer_tokens(texte):
    """Estimation rapide basée sur le nombre de mots (1 mot ~ 1.3 token en français)."""
    if not texte:
        return 0
    return max(1, int(len(str(texte).split()) * 1.3))

def post(path, payload):
    req = urllib.request.Request(BASE + path, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
RUN = int(time.time())  # sessions neuves à chaque lancement

# Accumulateurs pour le bilan final
total_tokens_in = 0
total_tokens_out = 0
total_duree = 0.0

start_global = time.time()

for i in range(n):
    sid = f"test-{RUN}-{i}"
    post("/profile", {"session_id": sid, "name": f"Client Test {i}", "email": f"client{i}@example.com",
                      "allergies": "noisettes", "children_ages": "6, 9"})
    
    for msg in SCENARIO:
        t0 = time.time()
        res = post("/chat", {"session_id": sid, "message": msg})
        t1 = time.time()
        duree = t1 - t0
        total_duree += duree

        reponse_texte = res.get("response") or res.get("message") or str(res)
        
        tokens_in = res.get("prompt_eval_count") or estimer_tokens(msg)
        tokens_out = res.get("eval_count") or estimer_tokens(reponse_texte)
        
        total_tokens_in += tokens_in
        total_tokens_out += tokens_out

# Calculs globaux de production (Cloud)
total_messages = n * len(SCENARIO)
total_tokens = total_tokens_in + total_tokens_out

cout_prod_in = (total_tokens_in / 1000) * TARIF_IN_PER_1K
cout_prod_out = (total_tokens_out / 1000) * TARIF_OUT_PER_1K
cout_total_prod = cout_prod_in + cout_prod_out

empreinte_co2_g = (total_tokens / 1000) * CARBONE_PER_1K_TOKENS


# --- AFFICHAGE DU RAPPORT D'ÉVALUATION ---
print(f"\n{'='*20} MESURES DU TEST {'='*20}")
print(f"Messages envoyés       : {total_messages} ({n} session(s))")
print(f"Temps total d'exécution : {total_duree:.2f} s (moyenne : {total_duree/total_messages:.2f} s/msg)")
print(f"Tokens consommés       : {total_tokens} total ({total_tokens_in} in / {total_tokens_out} out)")
print(f"Coût estimé en Prod    : {cout_total_prod:.5f} € (pour {total_messages} msgs)")
print(f"Empreinte carbone Prod : {empreinte_co2_g:.4f} gCO2e")
print(f"{'='*57}\n")


# --- PROJECTION POUR LE CLIENT (100 000 requêtes/mois) ---
proj_req = 100000
facteur_proj = proj_req / total_messages
print(f"PROJECTION PROD POUR {proj_req:,} MESSAGES/MOIS :")
print(f"- Volume de tokens  : {int(total_tokens * facteur_proj):,} tokens/mois")
print(f"- Coût estimé API   : {cout_total_prod * facteur_proj:.2f} €/mois")
print(f"- Empreinte carbone : {(empreinte_co2_g * facteur_proj) / 1000:.2f} kg CO2e/mois")
print("="*57)