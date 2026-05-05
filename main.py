import os
import json
import asyncio
import hashlib
import requests
from typing import List
from datetime import datetime, timedelta
from plyer import notification
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

CONFIG_FILE = "config.json"

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

async def check_website(settings: Settings, url: str, last_hash: str):
    try:
        # requests.get yra sinchroninė funkcija, todėl vykdome to_thread, kad neblokuotume event loop
        response = await asyncio.to_thread(requests.get, url, timeout=10)
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
            tasks.append(check_website(settings, url, monitor_state[url]["last_hash"]))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, result in zip(settings.urls, results):
            if not isinstance(result, Exception):
                monitor_state[url]["last_hash"] = result
        
        total_sleep = settings.interval_minutes * 60
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