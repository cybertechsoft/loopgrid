import json
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
r=c.post('/api/v1/demo/refund')
r.raise_for_status()
print(json.dumps(r.json(),indent=2))
