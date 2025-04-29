import requests


def test_health_check():
    base_url = "http://localhost:8000"

    response = requests.get(base_url + "/docs")
    assert response.status_code == 200, "FastAPI no responde en /docs correctamente."
