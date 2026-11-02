"""AION MEMORY: local-first chat archive, evidence-backed memories and graph."""
import os, json, sqlite3, uuid, datetime, re
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

load_dotenv()
DB = Path(os.getenv("AION_DB_PATH", "data/aion.sqlite3"))
app = FastAPI(title="AION MEMORY", version="0.1.0")
origins = os.getenv("AION_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET","POST","DELETE"], allow_headers=["Content-Type"])

@contextmanager
def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
        db.commit()
    finally:
        db.close()

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())

def init():
    with conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,subject TEXT NOT NULL,predicate TEXT NOT NULL,object TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'candidate',created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_messages_chat ON messages(chat_id,created_at);
        CREATE INDEX IF NOT EXISTS ix_memories_subject ON memories(subject);
        """)

@app.on_event("startup")
def startup(): init()

class ChatIn(BaseModel):
    title: str = Field(default="Новый чат", min_length=1,max_length=200)
class MessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant|system|tool)$")
    content: str = Field(min_length=1,max_length=1000000)
class MemoryIn(BaseModel):
    message_id: str
    subject: str = Field(min_length=1,max_length=500)
    predicate: str = Field(min_length=1,max_length=200)
    object: str = Field(min_length=1,max_length=2000)
class AskIn(BaseModel):
    chat_id: str
    prompt: str = Field(min_length=1,max_length=100000)
    use_memory: bool = True

@app.get("/api/health")
def health(): return {"ok":True,"version":"0.1.0","cloud_configured":bool(os.getenv("AION_CLOUD_BASE_URL") and os.getenv("AION_CLOUD_API_KEY") and os.getenv("AION_CLOUD_MODEL"))}
@app.get("/api/chats")
def chats():
    with conn() as db: return [dict(x) for x in db.execute("SELECT * FROM chats ORDER BY created_at DESC")]
@app.post("/api/chats")
def new_chat(body:ChatIn):
    item={"id":uid(),"title":body.title,"created_at":now()}
    with conn() as db: db.execute("INSERT INTO chats VALUES (:id,:title,:created_at)",item)
    return item
@app.get("/api/chats/{chat_id}/messages")
def messages(chat_id:str):
    with conn() as db: return [dict(x) for x in db.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY created_at,id",(chat_id,))]
@app.post("/api/chats/{chat_id}/messages")
def add_message(chat_id:str,body:MessageIn):
    item={"id":uid(),"chat_id":chat_id,"role":body.role,"content":body.content,"created_at":now()}
    with conn() as db:
        if not db.execute("SELECT 1 FROM chats WHERE id=?",(chat_id,)).fetchone(): raise HTTPException(404,"Chat not found")
        db.execute("INSERT INTO messages VALUES (:id,:chat_id,:role,:content,:created_at)",item)
    return item
@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id:str):
    with conn() as db:
        result=db.execute("DELETE FROM chats WHERE id=?",(chat_id,))
        if not result.rowcount: raise HTTPException(404,"Chat not found")
    return {"deleted":True}
@app.post("/api/memories")
def add_memory(body:MemoryIn):
    item={"id":uid(),**body.model_dump(),"status":"candidate","created_at":now()}
    with conn() as db:
        if not db.execute("SELECT 1 FROM messages WHERE id=?",(body.message_id,)).fetchone(): raise HTTPException(404,"Source message not found")
        db.execute("INSERT INTO memories VALUES (:id,:message_id,:subject,:predicate,:object,:status,:created_at)",item)
    return item
@app.get("/api/memories")
def memories(q:str="",limit:int=100):
    limit=min(max(limit,1),500)
    with conn() as db:
        return [dict(x) for x in db.execute("SELECT * FROM memories WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ? ORDER BY created_at DESC LIMIT ?",tuple(["%"+q+"%"]*3+[limit]))]
@app.get("/api/graph")
def graph():
    with conn() as db: items=[dict(x) for x in db.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT 1000")]
    nodes={}
    edges=[]
    for m in items:
        a="subject:"+m["subject"].lower(); b="object:"+m["object"].lower()
        nodes[a]={"id":a,"label":m["subject"],"kind":"subject"}
        nodes[b]={"id":b,"label":m["object"],"kind":"object"}
        edges.append({"id":m["id"],"source":a,"target":b,"label":m["predicate"],"message_id":m["message_id"]})
    return {"nodes":list(nodes.values()),"edges":edges}
@app.get("/api/stats")
def stats():
    with conn() as db:
        return {t:db.execute("SELECT count(*) FROM "+t).fetchone()[0] for t in ("chats","messages","memories")}
@app.get("/api/search")
def search(q:str,limit:int=50):
    if not q.strip(): return []
    with conn() as db:
        return [dict(x) for x in db.execute("SELECT * FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",("%"+q+"%",min(max(limit,1),100)))]
@app.post("/api/ask")
async def ask(body:AskIn):
    base=os.getenv("AION_CLOUD_BASE_URL","").rstrip("/")
    key=os.getenv("AION_CLOUD_API_KEY","")
    model=os.getenv("AION_CLOUD_MODEL","")
    if not (base and key and model): raise HTTPException(503,"Configure Cloud API in local .env")
    if not base.startswith("https://"): raise HTTPException(400,"Cloud API endpoint must use HTTPS")
    with conn() as db:
        if not db.execute("SELECT 1 FROM chats WHERE id=?",(body.chat_id,)).fetchone(): raise HTTPException(404,"Chat not found")
        history=[dict(x) for x in db.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY created_at DESC LIMIT 20",(body.chat_id,))]
        candidates=[dict(x) for x in db.execute("SELECT subject,predicate,object,message_id FROM memories WHERE status='confirmed' ORDER BY created_at DESC LIMIT 30")] if body.use_memory else []
    context="\n".join(f"{x['subject']} | {x['predicate']} | {x['object']} (source {x['message_id']})" for x in candidates)
    msgs=[{"role":"system","content":"Use verified memories only as context, cite source message IDs when relying on them. Do not treat candidate memories as verified.\n"+context}]
    msgs += [x for x in reversed(history) if x["role"] in ("user","assistant")]
    msgs.append({"role":"user","content":body.prompt})
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(base+"/chat/completions",headers={"Authorization":"Bearer "+key},json={"model":model,"messages":msgs})
            response.raise_for_status()
            answer=response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError,KeyError,IndexError,ValueError) as e: raise HTTPException(502,"Model provider request failed") from e
    add_message(body.chat_id,MessageIn(role="user",content=body.prompt))
    add_message(body.chat_id,MessageIn(role="assistant",content=answer))
    return {"answer":answer}


# Memory operations: explicit review, safe export/import and SQLite-consistent backups.
from typing import Literal
from fastapi.responses import Response
import io
import zipfile
import hashlib

class ReviewIn(BaseModel):
    status: Literal["confirmed","rejected","candidate"]

class ImportIn(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    messages: list[MessageIn] = Field(min_length=1,max_length=10000)

class ExtractionIn(BaseModel):
    message_id: str

@app.patch("/api/memories/{memory_id}")
def review_memory(memory_id: str, body: ReviewIn):
    with conn() as db:
        row=db.execute("UPDATE memories SET status=? WHERE id=? RETURNING *",(body.status,memory_id)).fetchone()
        if row is None: raise HTTPException(404,"Memory not found")
        return dict(row)

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str):
    with conn() as db:
        cur=db.execute("DELETE FROM memories WHERE id=?",(memory_id,))
        if not cur.rowcount: raise HTTPException(404,"Memory not found")
    return {"deleted":True}

@app.post("/api/import")
def import_chat(body: ImportIn):
    chat={"id":uid(),"title":body.title,"created_at":now()}
    with conn() as db:
        db.execute("INSERT INTO chats VALUES (:id,:title,:created_at)",chat)
        for msg in body.messages:
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?)",(uid(),chat["id"],msg.role,msg.content,now()))
    return {"chat_id":chat["id"],"imported":len(body.messages)}

@app.get("/api/chats/{chat_id}/export")
def export_chat(chat_id: str):
    with conn() as db:
        row=db.execute("SELECT * FROM chats WHERE id=?",(chat_id,)).fetchone()
        if row is None: raise HTTPException(404,"Chat not found")
        items=[dict(m) for m in db.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY created_at,id",(chat_id,))]
    payload=json.dumps({"format":"aion-chat-v1","chat":dict(row),"messages":items},ensure_ascii=False,indent=2)
    return Response(content=payload,media_type="application/json",headers={"Content-Disposition":f'attachment; filename="aion-chat-{chat_id}.json"'})

@app.post("/api/memories/extract")
async def extract_memory(body: ExtractionIn):
    """Model-assisted extraction; never confirms model output automatically."""
    base=os.getenv("AION_CLOUD_BASE_URL","").rstrip("/")
    key=os.getenv("AION_CLOUD_API_KEY","")
    model=os.getenv("AION_CLOUD_MODEL","")
    if not (base and key and model): raise HTTPException(503,"Cloud model not configured")
    if not base.startswith("https://"): raise HTTPException(400,"HTTPS required")
    with conn() as db:
        msg=db.execute("SELECT * FROM messages WHERE id=?",(body.message_id,)).fetchone()
        if msg is None: raise HTTPException(404,"Source message not found")
        content=msg["content"]
    prompt="Extract up to 10 explicit factual triples from this text. Return ONLY a JSON array of objects with keys subject,predicate,object. Do not infer unstated facts. Text follows:\\n"+content
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(base+"/chat/completions",headers={"Authorization":"Bearer "+key},json={"model":model,"messages":[{"role":"user","content":prompt}]})
            response.raise_for_status()
            raw=response.json()["choices"][0]["message"]["content"]
            triples=json.loads(raw)
    except (httpx.HTTPError,KeyError,IndexError,ValueError,TypeError) as exc:
        raise HTTPException(502,"Extraction provider returned an invalid response") from exc
    if not isinstance(triples,list): raise HTTPException(502,"Expected JSON array")
    created=[]
    for triple in triples[:10]:
        if not isinstance(triple,dict): continue
        try:
            item=MemoryIn(message_id=body.message_id,subject=triple["subject"],predicate=triple["predicate"],object=triple["object"])
        except (KeyError,ValueError,TypeError): continue
        created.append(add_memory(item))
    return {"candidates":created,"requires_review":True}

@app.post("/api/backups")
def create_backup():
    """Local-only SQLite online backup; not exposed as a downloadable public endpoint."""
    folder=DB.parent/"backups"
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/("aion-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uid()[:8]+".sqlite3")
    with conn() as db:
        destination=sqlite3.connect(target)
        try: db.backup(destination)
        finally: destination.close()
    return {"created":True,"filename":target.name,"size_bytes":target.stat().st_size}

@app.get("/api/backups")
def list_backups():
    folder=DB.parent/"backups"
    if not folder.exists(): return []
    return [{"filename":p.name,"size_bytes":p.stat().st_size} for p in sorted(folder.glob("aion-*.sqlite3"),reverse=True)]
