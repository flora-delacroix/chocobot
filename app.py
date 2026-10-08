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


class ProfileIn(BaseModel):
    session_id: str
    name: str = ""
    email: str = ""
    allergies: str = ""
    children_ages: str = ""


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.post("/profile")
def profile(body: ProfileIn):
    db.save_customer(body.session_id, body.name, body.email, body.allergies, body.children_ages)
    return {"status": "saved"}


@app.post("/chat")
def chat(body: ChatIn):
    return handle_chat(body.session_id, body.message)


# Back-office de l'équipe Delcourt : pratique pour voir qui a écrit quoi
@app.get("/admin")
def admin():
    return FileResponse("static/admin.html")


@app.get("/admin/data")
def admin_data():
    data = db.get_all()
    data["llm"] = {"big": llm.BIG_MODEL, "small": llm.SMALL_MODEL}
    return data


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