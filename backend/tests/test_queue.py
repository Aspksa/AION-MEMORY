from pathlib import Path
from fastapi.testclient import TestClient
import backend.app as module

def test_queue_opt_in_and_retry(tmp_path,monkeypatch):
    monkeypatch.setattr(module,"DB",tmp_path/"queue.sqlite3")
    monkeypatch.setenv("AION_AUTO_EXTRACT","1")
    module.init()
    with TestClient(module.app) as client:
        chat=client.post("/api/chats",json={"title":"queue"}).json()
        client.post(f"/api/chats/{chat['id']}/messages",json={"role":"user","content":"Important fact"})
        jobs=client.get("/api/jobs").json()
        assert len(jobs)==1
        assert jobs[0]["status"]=="pending"
        assert client.post(f"/api/jobs/{jobs[0]['id']}/retry").status_code==409
        assert client.get("/api/knowledge/search?q=important").json()==[]
