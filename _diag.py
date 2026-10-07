# Diagnosa GET /decisions 500: body respons + log server.
import json

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app, raise_server_exceptions=False) as c:
    r = c.get("/decisions")
    print("TAG|status=%d" % r.status_code)
    print("TAG|body=%s" % r.text[:300])
