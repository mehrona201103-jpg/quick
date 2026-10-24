import os, json, hmac, hashlib, time
from urllib.parse import parse_qsl
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app import db
from app.market import analyze, candles, SYMBOLS, TIMEFRAMES, EXPIRIES
app=FastAPI(title="QUICK TRADER AI V3")
db.init()

def verify_webapp_user(request: Request, claimed_tg_id: int):
    token=os.getenv("BOT_TOKEN", "")
    raw=request.headers.get("X-Telegram-Init-Data", "")
    if not token or not raw:
        raise HTTPException(401, "Откройте WebApp через Telegram-бота")
    data=dict(parse_qsl(raw, keep_blank_values=True))
    received_hash=data.pop("hash", "")
    if not received_hash:
        raise HTTPException(401, "Нет подписи Telegram WebApp")
    check="\n".join(f"{k}={v}" for k,v in sorted(data.items()))
    secret=hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "Неверная подпись Telegram WebApp")
    try:
        auth_date=int(data.get("auth_date", "0"))
        user=json.loads(data.get("user", "{}"))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Некорректные данные Telegram WebApp")
    if auth_date < int(time.time())-86400 or auth_date > int(time.time())+60:
        raise HTTPException(401, "Данные Telegram устарели. Закройте и снова откройте WebApp.")
    if int(user.get("id", 0)) != int(claimed_tg_id):
        raise HTTPException(403, "ID аккаунта не совпадает с Telegram")
    return user

class AnalyzeRequest(BaseModel):
    tg_id:int
    symbol:str="EUR/USD"
    timeframe:str="1m"
    expiry:str="5m"
@app.get("/",response_class=HTMLResponse)
def home():
    return HTMLResponse(open("app/templates/index.html",encoding="utf-8").read())
@app.get("/api/webapp/profile")
def profile(request: Request, tg_id:int):
    verify_webapp_user(request, tg_id)
    u=db.get_user(tg_id)
    if not u: raise HTTPException(404,"Пользователь не зарегистрирован в боте")
    a=db.access_status(tg_id)
    return {"id":u["tg_id"],"username":u["username"],"pocket_id":u["pocket_id"],"approved":bool(u["approved"]),"blocked":bool(u["blocked"]),**a}
@app.get("/api/webapp/config")
def config(): return {"symbols":SYMBOLS,"timeframes":list(TIMEFRAMES),"expiries":EXPIRIES,"bot_username":os.getenv("BOT_USERNAME", ""),"author_id":os.getenv("AUTHOR_TELEGRAM_ID", "8383354229")}
@app.get("/api/webapp/history")
def get_history(request: Request, tg_id:int):
    verify_webapp_user(request, tg_id)
    return [dict(x) for x in db.history(tg_id)]
@app.post("/api/webapp/analyze")
async def web_analyze(req:AnalyzeRequest, request: Request):
    verify_webapp_user(request, req.tg_id)
    u=db.get_user(req.tg_id)
    if not u or not u["approved"] or u["blocked"]: raise HTTPException(403,"Сначала завершите регистрацию в боте")
    access=db.access_status(req.tg_id)
    if not access["allowed"]: raise HTTPException(402,"Бесплатный доступ закончился. Откройте меню тарифов в боте.")
    if req.symbol not in SYMBOLS: raise HTTPException(400,"Неизвестный инструмент")
    if req.timeframe not in TIMEFRAMES: raise HTTPException(400,"Неизвестный таймфрейм")
    if req.expiry not in EXPIRIES: raise HTTPException(400,"Неизвестная экспирация")
    try: s=await analyze(req.symbol,req.timeframe,req.expiry)
    except Exception as e: raise HTTPException(502,str(e))
    db.add_signal(req.tg_id,s)
    return s
@app.get("/api/webapp/chart")
async def chart(symbol:str="EUR/USD",timeframe:str="1m"):
    try: return {"symbol":symbol,"timeframe":timeframe,"candles":await candles(symbol,timeframe,60)}
    except Exception as e: raise HTTPException(502,str(e))
@app.get("/admin/stats")
def admin_stats(token:str=""):
    admin_token=os.getenv("ADMIN_PANEL_TOKEN", "")
    if not admin_token or token != admin_token: raise HTTPException(403,"Forbidden")
    return db.stats()
