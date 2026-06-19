import sys
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import os
from fastapi import HTTPException
from pydantic import BaseModel
import sys

if 'collections.Mapping' not in sys.modules:
    import collections
    if not hasattr(collections, 'Mapping'):
        class Mapping: pass
        collections.Mapping = Mapping

from SimConnect import Event
from simconnect_mobiflight import SimConnectMobiFlight
from mobiflight_variable_requests import MobiFlightVariableRequests

sm = None
mf = None
event_cache = {}

COMMUNITY_DIR = "community_folder"
os.makedirs(COMMUNITY_DIR, exist_ok=True)


def _quiet_proactor_exception_handler(loop, context):
    """Windows' ProactorEventLoop logs a harmless ConnectionResetError from its
    own internal cleanup callback (_call_connection_lost) whenever a WebSocket
    client disconnects abruptly (refresh, tab close, sleep/wake). It happens
    after our WebSocketDisconnect handling has already run, so it's just log
    noise — swallow it here and let everything else through normally."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sm, mf

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_quiet_proactor_exception_handler)

    try:
        sm = SimConnectMobiFlight()
        mf = MobiFlightVariableRequests(sm)
        mf.clear_sim_variables()
        await asyncio.sleep(1.5)
        mf.get("(A:AIRSPEED INDICATED, Knots)")
        print("Data link established and pipeline warmed.")
    except Exception as e:
        print(f"Connection failed: {e}")

    yield

    if sm:
        sm.exit()

app = FastAPI(lifespan=lifespan)  # ← only one definition, with lifespan attached

app.mount("/fonts", StaticFiles(directory="fonts"), name="fonts")

def execute_action(event_name: str):
    if not event_name or not event_name.strip():
        return
    global sm, mf, event_cache
    try:
        if any(char in event_name for char in ["(", ")", ">", " "]):
            if mf:
                mf.set(event_name)
        else:
            if event_name not in event_cache:
                event_cache[event_name] = Event(bytes(event_name, "utf-8"), sm)
            event_cache[event_name]()
    except Exception as e:
       print(f"Action Error: {e}")

def read_output(rpn: str) -> float:
    global mf
    try:
        val = mf.get(rpn)
        return val if val is not None else -1.0
    except Exception as e:
        print(f"Read error [{rpn[:40]}...]: {e}")
        return -1.0
    
class SaveRequest(BaseModel):
    filename: str
    data: dict

def _safe_json_path(filename: str) -> str:
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".json"):
        safe_name += ".json"
    return os.path.join(COMMUNITY_DIR, safe_name)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

@app.get("/community/list")
def list_community_files():
    files = [f for f in os.listdir(COMMUNITY_DIR) if f.endswith(".json")]
    return {"files": files}

@app.get("/community/file/{filename}")
def get_community_file(filename: str):
    path = _safe_json_path(filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/community/save")
def save_community_file(req: SaveRequest):
    path = _safe_json_path(req.filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(req.data, f, indent=2)
    return {"status": "saved", "filename": os.path.basename(path)}

@app.delete("/community/file/{filename}")
def delete_community_file(filename: str):
    path = _safe_json_path(filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    os.remove(path)
    return {"status": "deleted"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected.")

    local_registered_outputs: dict[str, float] = {}
    last_values: dict[str, float] = {}

    if mf:
        mf.clear_sim_variables()

    async def push_updates():
        while True:
            try:
                if mf and local_registered_outputs:
                    for rpn in list(local_registered_outputs.keys()):
                        val = read_output(rpn)
                        if val == -999.0:
                            val = 0.0
                        if last_values.get(rpn) != val:
                            last_values[rpn] = val
                            await websocket.send_text(json.dumps({
                                "type": "WASM_UPDATE",
                                "rpn": rpn,
                                "value": val
                            }))
            except Exception:
                break
            await asyncio.sleep(0.2)

    update_task = asyncio.create_task(push_updates())

    try:
        while True:
            text_data = await websocket.receive_text()
            msg = json.loads(text_data)

            if msg["type"] == "EXECUTE_ACTION":
                execute_action(msg["event"])
            elif msg["type"] == "REGISTER_OUTPUT":
                rpn = msg["rpn"]
                if rpn not in local_registered_outputs:
                    local_registered_outputs[rpn] = -999.0
                   #print(f"Registered output: {rpn[:60]}")
            elif msg["type"] == "UNREGISTER_OUTPUT":
                rpn = msg["rpn"]
                local_registered_outputs.pop(rpn, None)
                last_values.pop(rpn, None)

    except WebSocketDisconnect:
        print("WebSocket client disconnected.")
    finally:
        update_task.cancel()

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

app.mount("/fonts", StaticFiles(directory=os.path.join(BASE_DIR, "fonts")), name="fonts")

@app.get("/flight_stratum_icon_only.ico")
def get_favicon():
    return FileResponse(os.path.join(BASE_DIR, "flight_stratum_icon_only.ico"))

@app.get("/flight_stratum_icon_only.png")
def get_logo_png():
    return FileResponse(os.path.join(BASE_DIR, "flight_stratum_icon_only.png"))
...
COMMUNITY_DIR = os.path.join(BASE_DIR, "community_folder")
...
@app.get("/")
def get_index():
    with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

CURRENT_PORT = 8050 

@app.get("/config")
def get_config():
    return {"port": CURRENT_PORT}

def get_lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def run_server(port):
    """Blocking call — run uvicorn on the given port. Called from a background thread by gui.py."""
    global CURRENT_PORT
    CURRENT_PORT = port
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False, log_level="warning")

if __name__ == "__main__":
    run_server(8050)