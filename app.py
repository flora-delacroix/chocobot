from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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
    session_id: str
    message: str


class SignupIn(BaseModel):
    email: str
    mot_de_passe: str


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.post("/signup")
def signup(body: SignupIn):
    db.save_user(body.email, body.mot_de_passe)
    return {"status": "signup_ok"}


@app.post("/login")
def login(body: SignupIn):
    user = db.get_user(body.email)
    if not user:
        return {"status": "error", "message": "user_not_found"}, 401
    if not db.verify_password(body.mot_de_passe, user["mot_de_passe_hash"]):
        return {"status": "error", "message": "wrong_password"}, 401
    return {"status": "login_ok"}


@app.post("/chat")
def chat(body: ChatIn):
    return handle_chat(None, body.message)  # Chat anonyme (pas d'email)


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