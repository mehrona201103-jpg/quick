import os, httpx, math, asyncio
from time import monotonic
API_KEY=os.getenv("TWELVE_DATA_API_KEY","")
_CACHE={}
_CACHE_LOCK=asyncio.Lock()
_CACHE_SECONDS=55
SYMBOLS=[
"EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","NZD/USD",
"EUR/GBP","EUR/JPY","EUR/CHF","EUR/AUD","EUR/CAD","EUR/NZD","EUR/SEK","EUR/NOK","EUR/PLN","EUR/TRY",
"GBP/JPY","GBP/CHF","GBP/AUD","GBP/CAD","GBP/NZD","GBP/SGD","GBP/TRY",
"AUD/JPY","AUD/CHF","AUD/CAD","AUD/NZD","AUD/SGD","AUD/HKD",
"NZD/JPY","NZD/CHF","NZD/CAD","NZD/SGD","CAD/JPY","CAD/CHF","CHF/JPY","SGD/JPY","USD/SGD","USD/HKD","USD/CNH","USD/MXN","USD/ZAR","USD/TRY","USD/PLN","USD/SEK","USD/NOK",
"XAU/USD","XAG/USD","BTC/USD","ETH/USD","LTC/USD","XRP/USD","BCH/USD"
]
TIMEFRAMES={"1m":"1min","5m":"5min","15m":"15min","30m":"30min","1h":"1h","4h":"4h","1d":"1day"}
EXPIRIES=["5s","15s","30s","1m","5m","10m","15m","30m","1d"]
async def candles(symbol="EUR/USD", timeframe="1m", outputsize=100):
    if not API_KEY: raise RuntimeError("Не задан TWELVE_DATA_API_KEY")
    interval=TIMEFRAMES.get(timeframe,"1min")
    key=(symbol,interval)
    now=monotonic()
    cached=_CACHE.get(key)
    if cached and now-cached[0] < _CACHE_SECONDS:
        return cached[1][-outputsize:]
    async with _CACHE_LOCK:
        now=monotonic(); cached=_CACHE.get(key)
        if cached and now-cached[0] < _CACHE_SECONDS:
            return cached[1][-outputsize:]
        async with httpx.AsyncClient(timeout=15) as client:
            r=await client.get("https://api.twelvedata.com/time_series",params={"symbol":symbol,"interval":interval,"outputsize":100,"apikey":API_KEY})
            r.raise_for_status(); data=r.json()
        if "values" not in data: raise RuntimeError(data.get("message","Поставщик не вернул свечи"))
        values=list(reversed(data["values"]))
        _CACHE[key]=(monotonic(),values)
        return values[-outputsize:]
def ema(values, period):
    k=2/(period+1); out=[float(values[0])]
    for v in values[1:]: out.append(float(v)*k+out[-1]*(1-k))
    return out
def rsi(values, period=14):
    dif=[values[i]-values[i-1] for i in range(1,len(values))]
    ups=[max(x,0) for x in dif]; downs=[max(-x,0) for x in dif]
    if len(dif)<period: return 50
    avg_u=sum(ups[-period:])/period; avg_d=sum(downs[-period:])/period
    if avg_d==0: return 100
    return 100-100/(1+avg_u/avg_d)
async def analyze(symbol="EUR/USD", timeframe="1m", expiry="5m"):
    rows=await candles(symbol,timeframe,100)
    closes=[float(x["close"]) for x in rows]
    if len(closes)<30: raise RuntimeError("Недостаточно свечей для анализа")
    e9,e21=ema(closes,9),ema(closes,21); rv=rsi(closes)
    momentum=closes[-1]-closes[-4]
    votes=(1 if e9[-1]>e21[-1] else -1)+(1 if momentum>0 else -1)+(1 if rv>52 else -1 if rv<48 else 0)
    side="BUY" if votes>=2 else "SELL" if votes<=-2 else "WAIT"
    strength=round(50+abs(votes)*12) if side!="WAIT" else 50
    why=("EMA и импульс вверх" if side=="BUY" else "EMA и импульс вниз" if side=="SELL" else "Сигналы смешанные")
    # This is indicator agreement, not a statistically validated probability of success.
    return {"symbol":symbol,"timeframe":timeframe,"expiry":expiry,"side":side,
      "confidence":min(86,strength),"explanation":why,"price":closes[-1],
      "rsi":round(rv,1),"ema9":round(e9[-1],6),"ema21":round(e21[-1],6),
      "timestamp":rows[-1].get("datetime",""),"source":"Twelve Data · обычный Forex"}
