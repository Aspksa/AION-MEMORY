import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
import backend.app as module

def test_archive_graph():
    with tempfile.TemporaryDirectory() as folder:
        module.DB=Path(folder)/"test.sqlite3"
        module.init()
        with TestClient(module.app) as client:
            chat=client.post("/api/chats",json={"title":"Test"}).json()
            msg=client.post(f"/api/chats/{chat['id']}/messages",json={"role":"user","content":"Remember this"}).json()
            assert client.get(f"/api/chats/{chat['id']}/messages").json()[0]["content"]=="Remember this"
            memory=client.post("/api/memories",json={"message_id":msg["id"],"subject":"AION","predicate":"stores","object":"chats"}).json()
            assert memory["status"]=="candidate"
            assert len(client.get("/api/graph").json()["edges"])==1
            assert len(client.get("/api/search?q=Remember").json())==1
            assert client.delete(f"/api/chats/{chat['id']}").status_code==200
            assert client.get("/api/memories").json()==[]
