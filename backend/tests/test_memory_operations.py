from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
import backend.app as module

def test_import_review_export_backup():
    with tempfile.TemporaryDirectory() as tmp:
        module.DB=Path(tmp)/"aion.sqlite3"
        module.init()
        with TestClient(module.app) as client:
            result=client.post("/api/import",json={"title":"Импорт","messages":[{"role":"user","content":"Тест памяти"}]})
            assert result.status_code==200
            chat_id=result.json()["chat_id"]
            messages=client.get(f"/api/chats/{chat_id}/messages").json()
            assert len(messages)==1
            record=client.post("/api/memories",json={"message_id":messages[0]["id"],"subject":"AION","predicate":"stores","object":"chat"})
            assert record.status_code==200
            memory_id=record.json()["id"]
            assert client.patch(f"/api/memories/{memory_id}",json={"status":"confirmed"}).json()["status"]=="confirmed"
            exported=client.get(f"/api/chats/{chat_id}/export").json()
            assert exported["messages"][0]["content"]=="Тест памяти"
            assert client.post("/api/backups").json()["created"]
            assert len(client.get("/api/backups").json())==1
            assert client.delete(f"/api/memories/{memory_id}").status_code==200
