import os
import json
import asyncio
import hashlib
import requests
import random
from typing import List
from datetime import datetime, timedelta
from plyer import notification
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

CONFIG_FILE = "config.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0"
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

app_status = {
    "last_checked": None,
    "next_check": None,
    "urls_state": {},
    "events": [],
    "is_monitoring": False
}

monitor_state = {}

def add_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    app_status["events"].insert(0, f"[{timestamp}] {message}")
    if len(app_status["events"]) > 20:
        app_status["events"].pop()

class Settings(BaseModel):
    urls: List[str]
    interval_minutes: int
    webhook_url: str = ""
    use_local_notifications: bool = False

def load_settings():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return Settings(**data)
    except Exception:
        return None

def save_settings(settings: Settings):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.dict(), f, indent=4)

async def check_website(settings: Settings, url: str, last_hash: str, retry_count: int = 0):
    try:
        # requests.get yra sinchroninė funkcija, todėl vykdome to_thread, kad neblokuotume event loop
        response = await asyncio.to_thread(requests.get, url, headers=get_headers(), timeout=15)
        
        if response.status_code == 403 and retry_count < 1:
            add_event(f"403 Blokavimas ({url}) - bandoma vėl po 10s...")
            await asyncio.sleep(10)
            return await check_website(settings, url, last_hash, retry_count + 1)
            
        response.raise_for_status()
        
        content = response.text
        current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        now_iso = datetime.now().isoformat()
        app_status["last_checked"] = now_iso
        
        if "urls_state" not in app_status:
            app_status["urls_state"] = {}
        if url not in app_status["urls_state"]:
            app_status["urls_state"][url] = {}
        app_status["urls_state"][url]["last_checked"] = now_iso
        
        if last_hash is not None and current_hash != last_hash:
            add_event(f"Rastas pokytis: {url}")
            msg_text = f"🔔 Svetainės ({url}) turinys pasikeitė!"
            
            if settings.webhook_url:
                msg = {"content": msg_text}
                try:
                    await asyncio.to_thread(requests.post, settings.webhook_url, json=msg, timeout=10)
                    print(f"[{url}] Turinys pasikeitė! Pranešimas išsiųstas į Discord.")
                except Exception as e:
                    print(f"Nepavyko išsiųsti pranešimo į Discord: {e}")
                    
            if settings.use_local_notifications or not settings.webhook_url:
                try:
                    def show_notification():
                        notification.notify(
                            title="Svetainės Stebėtojas",
                            message=msg_text,
                            app_name="Svetainės Stebėtojas",
                            timeout=10
                        )
                    await asyncio.to_thread(show_notification)
                    print(f"[{url}] Parodytas vietinis pranešimas kompiuteryje.")
                except Exception as e:
                    print(f"Nepavyko parodyti vietinio pranešimo: {e}")
        elif last_hash is not None:
            add_event(f"Patikrinta ({url}) - pokyčių nėra")
        elif last_hash is None:
            add_event(f"Pirmas patikrinimas ({url}) - pradedamas stebėjimas")
            
        return current_hash
    except Exception as e:
        now_iso = datetime.now().isoformat()
        app_status["last_checked"] = now_iso
        if "urls_state" not in app_status:
            app_status["urls_state"] = {}
        if url not in app_status["urls_state"]:
            app_status["urls_state"][url] = {}
        app_status["urls_state"][url]["last_checked"] = now_iso
        
        add_event(f"Klaida ({url}): {str(e)}")
        print(f"Klaida tikrinant svetainę {url}: {e}")
        return last_hash

async def monitoring_task():
    while True:
        if not app_status["is_monitoring"]:
            app_status["next_check"] = None
            for url in app_status.get("urls_state", {}):
                app_status["urls_state"][url]["next_check"] = None
            await asyncio.sleep(1)
            continue

        settings = load_settings()
        
        if not settings or not settings.urls or settings.interval_minutes <= 0:
            app_status["next_check"] = None
            for url in app_status.get("urls_state", {}):
                app_status["urls_state"][url]["next_check"] = None
            await asyncio.sleep(10)
            continue
            
        if "urls_state" not in app_status:
            app_status["urls_state"] = {}
            
        for url in settings.urls:
            if url not in monitor_state:
                monitor_state[url] = {"last_hash": None}
            if url not in app_status["urls_state"]:
                app_status["urls_state"][url] = {"last_checked": None, "next_check": None}
                
        for url in list(monitor_state.keys()):
            if url not in settings.urls:
                del monitor_state[url]
        for url in list(app_status["urls_state"].keys()):
            if url not in settings.urls:
                del app_status["urls_state"][url]
                
        tasks = []
        for url in settings.urls:
            # Pridedame atsitiktinį vėlavimą prieš kiekvieną užklausą (2-7 sek.)
            delay = random.uniform(2, 7)
            await asyncio.sleep(delay)
            tasks.append(check_website(settings, url, monitor_state[url]["last_hash"]))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, result in zip(settings.urls, results):
            if not isinstance(result, Exception):
                monitor_state[url]["last_hash"] = result
        
        total_sleep = settings.interval_minutes * 60
        # Pridedame nedidelį atsitiktinumą prie bendro laukimo laiko (+/- 10%)
        total_sleep = total_sleep * random.uniform(0.9, 1.1)
        
        next_time = (datetime.now() + timedelta(seconds=total_sleep)).isoformat()
        app_status["next_check"] = next_time
        
        for url in settings.urls:
            app_status["urls_state"][url]["next_check"] = next_time
        
        # Miegoti mažais intervalais, kad greitai reaguotume į nustatymų pasikeitimus (pvz., pakeitus intervalą)
        slept = 0
        while slept < total_sleep:
            if not app_status["is_monitoring"]:
                break
            await asyncio.sleep(1)
            slept += 1
            
            if slept % 5 == 0:
                new_settings = load_settings()
                if new_settings and (new_settings.urls != settings.urls or new_settings.interval_minutes != settings.interval_minutes):
                    break

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fono užduoties paleidimas aplikacijos starto metu
    task = asyncio.create_task(monitoring_task())
    yield
    # Fono užduoties atšaukimas aplikacijos išjungimo metu
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def serve_ui():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html failas nerastas."}

@app.get("/api/settings", response_model=Settings)
def get_settings():
    settings = load_settings()
    if settings:
        return settings
    return Settings(urls=[], interval_minutes=5, webhook_url="", use_local_notifications=False)

@app.post("/api/settings")
def update_settings(settings: Settings):
    try:
        save_settings(settings)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ControlAction(BaseModel):
    action: str

@app.post("/api/control")
def control_monitoring(payload: ControlAction):
    action = payload.action
    if action == "start":
        app_status["is_monitoring"] = True
    elif action == "pause":
        app_status["is_monitoring"] = False
        app_status["next_check"] = None
        for url in app_status.get("urls_state", {}):
            app_status["urls_state"][url]["next_check"] = None
    elif action == "stop":
        app_status["is_monitoring"] = False
        app_status["next_check"] = None
        for url in app_status.get("urls_state", {}):
            app_status["urls_state"][url]["next_check"] = None
        monitor_state.clear()
    elif action == "clear":
        app_status["events"].clear()
        monitor_state.clear()
    else:
        raise HTTPException(status_code=400, detail="Nežinoma komanda")
    return {"status": "success", "is_monitoring": app_status["is_monitoring"]}

@app.get("/api/status")
def get_status():
    return app_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)