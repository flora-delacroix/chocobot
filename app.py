from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from chatbot import handle_chat
import db
import llm

app = FastAPI(title="ChocoBot - Maison Delcourt")
app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatIn(BaseModel):
    session_id: str
    message: str


class SignupIn(BaseModel):
    email: str
    mot_de_passe: str


class ProfileIn(BaseModel):
    session_id: str
    name: str = ""
    email: str = ""
    allergies: str = ""
    children_ages: str = ""


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
    return handle_chat(body.session_id, body.message)


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
    return {"status": "ok"}