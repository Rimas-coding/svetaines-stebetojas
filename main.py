import os
import json
import asyncio
import hashlib
import requests
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
    "events": [],
    "is_monitoring": False
}

monitor_state = {
    "last_hash": None,
    "last_url": None
}

def add_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    app_status["events"].insert(0, f"[{timestamp}] {message}")
    if len(app_status["events"]) > 20:
        app_status["events"].pop()

class Settings(BaseModel):
    url: str
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

async def check_website(settings: Settings, last_hash: str):
    try:
        # requests.get yra sinchroninė funkcija, todėl vykdome to_thread, kad neblokuotume event loop
        response = await asyncio.to_thread(requests.get, settings.url, timeout=10)
        response.raise_for_status()
        
        content = response.text
        current_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        app_status["last_checked"] = datetime.now().isoformat()
        
        if last_hash is not None and current_hash != last_hash:
            add_event("Rastas pokytis")
            msg_text = f"🔔 Svetainės ({settings.url}) turinys pasikeitė!"
            
            if settings.webhook_url:
                msg = {"content": msg_text}
                try:
                    await asyncio.to_thread(requests.post, settings.webhook_url, json=msg, timeout=10)
                    print(f"[{settings.url}] Turinys pasikeitė! Pranešimas išsiųstas į Discord.")
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
                    print(f"[{settings.url}] Parodytas vietinis pranešimas kompiuteryje.")
                except Exception as e:
                    print(f"Nepavyko parodyti vietinio pranešimo: {e}")
        elif last_hash is not None:
            add_event("Patikrinta - pokyčių nėra")
        elif last_hash is None:
            add_event("Pirmas patikrinimas - pradedamas stebėjimas")
            
        return current_hash
    except Exception as e:
        app_status["last_checked"] = datetime.now().isoformat()
        add_event(f"Klaida: {str(e)}")
        print(f"Klaida tikrinant svetainę {settings.url}: {e}")
        return last_hash

async def monitoring_task():
    while True:
        if not app_status["is_monitoring"]:
            app_status["next_check"] = None
            await asyncio.sleep(1)
            continue

        settings = load_settings()
        
        if not settings or not settings.url or settings.interval_minutes <= 0:
            app_status["next_check"] = None
            await asyncio.sleep(10)
            continue
            
        if settings.url != monitor_state["last_url"]:
            monitor_state["last_hash"] = None
            monitor_state["last_url"] = settings.url
            
        monitor_state["last_hash"] = await check_website(settings, monitor_state["last_hash"])
        
        total_sleep = settings.interval_minutes * 60
        app_status["next_check"] = (datetime.now() + timedelta(seconds=total_sleep)).isoformat()
        
        # Miegoti mažais intervalais, kad greitai reaguotume į nustatymų pasikeitimus (pvz., pakeitus intervalą)
        slept = 0
        while slept < total_sleep:
            if not app_status["is_monitoring"]:
                break
            await asyncio.sleep(1)
            slept += 1
            
            if slept % 5 == 0:
                new_settings = load_settings()
                if new_settings and (new_settings.url != settings.url or new_settings.interval_minutes != settings.interval_minutes):
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
    return Settings(url="", interval_minutes=5, webhook_url="", use_local_notifications=False)

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
    elif action == "stop":
        app_status["is_monitoring"] = False
        app_status["next_check"] = None
        monitor_state["last_hash"] = None
    elif action == "clear":
        app_status["events"].clear()
        monitor_state["last_hash"] = None
    else:
        raise HTTPException(status_code=400, detail="Nežinoma komanda")
    return {"status": "success", "is_monitoring": app_status["is_monitoring"]}

@app.get("/api/status")
def get_status():
    return app_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)