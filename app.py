from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from chatbot import handle_chat
import db, llm
import logging, sentry_sdk


logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

sentry_sdk.init(
    dsn="https://8462705d7931a9fbb5055da8265f964e@o4512220066676736.ingest.us.sentry.io/4512220093939712",
    send_default_pii=True,
)


app = FastAPI(title="ChocoBot - Maison Delcourt")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatIn(BaseModel):
    email: Optional[str] = None
    message: str


class SignupIn(BaseModel):
    email: str
    mot_de_passe: str


class PreferencesIn(BaseModel):
    email: str
    allergies_encrypted: Optional[str] = None
    tranche_age: Optional[str] = None


@app.get("/")
def home():
    response = FileResponse("static/index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post("/signup")
def signup(body: SignupIn):
    db.save_user(body.email, body.mot_de_passe)
    return {"status": "signup_ok"}


@app.post("/login")
def login(body: SignupIn):
    # Suppression automatique des comptes inactifs depuis 1 an
    db.delete_inactive_users(days=365)

    user = db.get_user(body.email)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "message": "user_not_found"})
    if not db.verify_password(body.mot_de_passe, user["mot_de_passe_hash"]):
        return JSONResponse(status_code=401, content={"status": "error", "message": "wrong_password"})

    # Mise à jour de la dernière activité
    db.update_activity(body.email)
    return {"status": "login_ok"}


@app.post("/chat")
def chat(body: ChatIn):
    # Mettre à jour l'activité si connecté
    if body.email:
        db.update_activity(body.email)
    return handle_chat(body.email, body.message)


@app.post("/update-preferences")
def update_preferences(body: PreferencesIn):
    """Met à jour les allergies et tranche d'âge."""
    user = db.get_user(body.email)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "message": "user_not_found"})

    db.update_preferences(body.email, body.allergies_encrypted, body.tranche_age)
    return {"status": "preferences_updated"}


@app.post("/delete-allergies")
def delete_allergies(body: SignupIn):
    """Supprime juste les allergies et la tranche d'âge."""
    user = db.get_user(body.email)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "message": "user_not_found"})
    if not db.verify_password(body.mot_de_passe, user["mot_de_passe_hash"]):
        return JSONResponse(status_code=401, content={"status": "error", "message": "wrong_password"})

    db.clear_allergies(body.email)
    return {"status": "allergies_deleted"}


@app.post("/delete")
def delete_account(body: SignupIn):
    """Supprime complètement le compte utilisateur."""
    user = db.get_user(body.email)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "message": "user_not_found"})
    if not db.verify_password(body.mot_de_passe, user["mot_de_passe_hash"]):
        return JSONResponse(status_code=401, content={"status": "error", "message": "wrong_password"})

    db.delete_user(body.email)
    return {"status": "account_deleted"}


@app.get("/admin")
def admin():
    return FileResponse("static/admin.html")


@app.get("/admin/data")
def admin_data():
    return {
        "stats": db.get_stats(),
        "llm": {"big": llm.BIG_MODEL, "small": llm.SMALL_MODEL}
    }


@app.get("/health")
def health():
    try:
        llm.chat(llm.SMALL_MODEL, [{"role": "user", "content": "ping"}], max_tokens=1)
        llm_status = "ok"
    except Exception:
        llm_status = "unreachable"

    return {
        "status": "ok" if llm_status == "ok" else "degraded",
        "llm": llm_status
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.warning(f"Donnée corrompue/invalide reçue sur {request.url.path} : {exc.errors()}")
    sentry_sdk.capture_message(f"Corrupted Payload on {request.url.path}: {exc.errors()}", level="warning")
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": "Les données envoyées sont invalides ou corrompues."}
    )