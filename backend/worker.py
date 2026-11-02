"""Background extraction worker. Explicit opt-in; candidates require review."""
import asyncio
import os
from backend.app import init,conn,now,extract_memory,ExtractionIn

async def run_once():
    with conn() as db:
        job=db.execute("SELECT id,message_id FROM extraction_jobs WHERE status='pending' ORDER BY created_at LIMIT 1").fetchone()
        if job is None: return False
        job=dict(job)
        db.execute("UPDATE extraction_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?",(now(),job["id"]))
    try:
        await extract_memory(ExtractionIn(message_id=job["message_id"]))
    except Exception as exc:
        with conn() as db:
            db.execute("UPDATE extraction_jobs SET status='failed',error=?,updated_at=? WHERE id=?",(str(exc)[:500],now(),job["id"]))
    else:
        with conn() as db:
            db.execute("UPDATE extraction_jobs SET status='done',updated_at=? WHERE id=?",(now(),job["id"]))
    return True

def recover_interrupted_jobs():
    with conn() as db:
        db.execute("UPDATE extraction_jobs SET status='pending',error='Recovered after restart',updated_at=? WHERE status='running'",(now(),))

async def main():
    init()
    recover_interrupted_jobs()
    print("AION extraction worker started")
    while True:
        if not await run_once():
            await asyncio.sleep(5)

if __name__=="__main__":
    asyncio.run(main())
