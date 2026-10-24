import os, threading, asyncio
import uvicorn
from app.bot import run_bot
def web():
    uvicorn.run("app.web:app", host="0.0.0.0", port=int(os.getenv("PORT","8000")))
if __name__ == "__main__":
    threading.Thread(target=web, daemon=True).start()
    asyncio.run(run_bot())
