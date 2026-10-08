import os
import pytest
from fastapi.testclient import TestClient
from app import app
from chatbot import is_simple_query, get_predifined_response

os.environ["SENTRY_DSN"] = ""

client = TestClient(app)

# --- 1. GREEN IT : ROUTAGE D'INTENTION ---
def test_routing_simple_vs_complex():
    assert is_simple_query("Bonjour") is True
    assert is_simple_query("Merci beaucoup") is True
    
    assert is_simple_query("Je voudrais un conseil pour du chocolat noir") is False
    assert is_simple_query("Quels sont les ingrédients du praliné ?") is False
    assert is_simple_query("Je cherche un coffret cadeau pour offrir à ma mère") is False


# --- 2. GREEN IT : CACHE FAQ ---
def test_faq_cache_hit():
    response = get_predifined_response("Quels sont vos horaires ?")
    assert response is not None
    
    response_unknown = get_predifined_response("Avez-vous des truffes au matcha ?")
    assert response_unknown is None


# --- 3. INFRASTRUCTURE : ENDPOINT /health ---
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "llm" in data


# --- 4. INCIDENT : CAPTURE PAYLOAD CORROMPU ---
def test_corrupted_payload_handling():
    response = client.post("/profile", json={"session_id": None, "email": 12345})
    
    assert response.status_code == 400
    assert response.json()["status"] == "error"