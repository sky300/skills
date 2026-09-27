# Chat Window Takeover (NapCat OneBot v11)

How an autonomous agent temporarily takes over a QQ private or group chat window to handle automated replies, without freezing the primary agent loop.

---

## 1. Core Architecture: Inversion of Control

### The Anti-Pattern
In standard tool-use execution, calling a long-running foreground tool (e.g. `while True: time.sleep(...)`) **blocks and suspends the primary agent model**. The agent cannot receive intermediate events, reason across turns, or formulate replies during tool execution. Doing so causes tool timeouts or completely stalls the conversation.

### The Decoupled Model (Sensor + Brain)
To allow the **current session's primary model** to generate each chat reply dynamically, the architecture must separate:
1. **Event Sensor (Inbound)**: A non-blocking background listener or webhook receiver that buffers, debounces, and filters incoming messages.
2. **Agent Trigger (Interrupt / Wake)**: An out-of-band notification or webhook callback that wakes the primary model for a single reasoning turn.
3. **Agent Action (Outbound)**: The model reasons over context, drafts the response, and calls `send_private_msg` / `send_group_msg` via HTTP.

---

## 2. Resolving "Me" (Zero-Guessing Rule)

> **Rule**: When filtering out the account's own messages, **never guess the account identity** by inspecting friend lists, scanning remarks, or reading chat history.

In OneBot v11:
- **WebSocket Events**: Every event envelope natively contains `self_id` (the bot's UIN). Comparing `event.get("user_id") == event.get("self_id")` instantly identifies own-messages.
- **HTTP API**: Calling `GET /get_login_info` returns `{"data": {"user_id": <uin>, "nickname": "..."}}`.

Always rely strictly on these two authorities.

---

## 3. Recommended Design: 5-Second Silence Debounce

Human conversation patterns on instant messaging platforms rarely resemble single complete paragraphs. Users frequently split one thought across 2 to 4 rapid short messages within a few seconds.

### Why Debounce is Critical
1. **Semantic Completeness**: Merging rapid fragments (e.g. "Wait", "Actually", "Can you check this?") into a single prompt preserves full conversational context.
2. **Anti-Risk & Account Safety**: Instant, robotic replies to every single short line will trigger Tencent's platform risk controls and result in temporary muting or account restriction.
3. **Token & Call Efficiency**: Prevents spinning up 4 separate model completions when 1 coherent response is needed.

### Standard Debounce Policy
- **Default Window**: **5.0 seconds of silence**.
- The sensor resets its silence countdown on each new message from the target conversation. Once 5.0 seconds elapse with no further incoming messages, the aggregated buffer is emitted as a single event.

---

## 4. In-Flight Concurrency: What Happens if a New Message Arrives During Generation?

A common edge case: *Message A arrives → 5s silence passes → Model begins generating Reply A → At second 7, Message B arrives.*

### Behavior in Single-Session / Queue-Based Runtimes (e.g. Hermes, Telegram)
- **Serialized Execution (No Parallel Race, No Cancellation)**:
  - The runtime does not cancel the in-flight Reply A. Reply A completes and is sent via HTTP API.
  - Message B (after its own 5s debounce) enters the event queue. Once Turn A completes, the runtime immediately wakes the model for Turn B.
  - **Result**: The agent sends Reply A, then immediately sees Message B alongside the logged history of Reply A, and produces a contextual follow-up Reply B.
  - **No collisions**: Because turns are strictly serialized, there are no overlapping network requests or out-of-order replies.

### Behavior in Stateless Webhook Environments
- If using independent serverless webhooks, two incoming webhooks could spin up concurrent containers.
- **Requirement**: Use a concurrency limit of 1 (or a FIFO queue / mutex lock per conversation) so Message B waits for Reply A to finish before being dispatched.

---

## 5. Enabling NapCat WebSocket Server

NapCat supports two distinct WebSocket server architectures:

### Architecture A: Shared Port via HTTP Server (Recommended)
NapCat's HTTP server adapter has built-in WebSocket support. When `enableWebsocket: true` is set under `httpServers`, WebSocket upgrade requests (`ws://<host>:<http_port>/`) are handled on the **exact same port** as HTTP.
- **No port conflicts**: Uses only one TCP port (e.g. `3001`).
- **Token**: Inherits `token` from the corresponding `httpServers` entry.
- **Important**: Keep `websocketServers: []` empty when using this mode. Do **not** add a `websocketServers` entry with the same port, as that would cause an `EADDRINUSE: address already in use` error.

```json
{
  "network": {
    "httpServers": [
      {
        "name": "httpServer",
        "enable": true,
        "port": 3001,
        "host": "0.0.0.0",
        "enableCors": true,
        "enableWebsocket": true,
        "messagePostFormat": "array",
        "token": "<access_token>",
        "debug": false
      }
    ],
    "websocketServers": []
  }
}
```

### Architecture B: Dedicated Standalone WebSocket Server
If you need an independent WebSocket server instance (e.g. custom heartbeat interval or isolated access token), set `enableWebsocket: false` on the HTTP server (or bind it to a **different port** like `3002`):

```json
{
  "network": {
    "httpServers": [
      {
        "name": "httpServer",
        "enable": true,
        "port": 3001,
        "host": "0.0.0.0",
        "enableCors": true,
        "enableWebsocket": false,
        "token": "<http_token>"
      }
    ],
    "websocketServers": [
      {
        "enable": true,
        "name": "websocket-server-1",
        "host": "0.0.0.0",
        "port": 3002,
        "reportSelfMessage": false,
        "enableForcePushEvent": true,
        "messagePostFormat": "array",
        "token": "<ws_token>",
        "debug": false,
        "heartInterval": 30000
      }
    ]
  }
}
```
**CRITICAL**: A port number cannot appear in both `httpServers` and `websocketServers` at the same time. Doing so will crash the WebSocket listener with `listen EADDRINUSE`.

### Mandatory Agent Interaction Rule
> **Rule**: If the user asks the agent to modify a NapCat instance to enable WebSocket servers or HTTP reporting, the agent **must ask the user for the instance deployment mode** (e.g. host bare-metal, Docker/Podman container, Systemd service) **and the exact configuration file path**. Never guess file paths or assume container layouts.

---

## 6. Standalone Python Sensor Template

This script acts as the background event sensor. It computes only what must be exact (parsing, debouncing, self-filtering, timeout) and contains no LLM code.

To run without dependency issues on modern systems with `uv`:
```bash
uv run --with websockets python3 takeover_sensor.py --url ws://127.0.0.1:3001 --token <token> --target group:778330249 --ttl 1800
```

### Template Code (`takeover_sensor.py`)
```python
#!/usr/bin/env python3
"""
Self-contained NapCat OneBot v11 WebSocket Takeover Sensor.
Listens to WebSocket events, debounces incoming messages by 5s,
filters self-sent messages, and emits 'TAKEOVER_EVENT <json>' to stdout.
"""
import sys
import json
import time
import asyncio
import inspect
import argparse

try:
    import websockets
except ImportError:
    sys.stderr.write("Error: 'websockets' library required. Run with: uv run --with websockets python3 ...\n")
    sys.exit(1)

MARKER_READY = "TAKEOVER_READY"
MARKER_EVENT = "TAKEOVER_EVENT"
MARKER_NOTICE = "TAKEOVER_NOTICE"
MARKER_EXIT = "TAKEOVER_EXIT"

def emit(marker, **fields):
    print(marker + " " + json.dumps(fields, ensure_ascii=False), flush=True)

async def monitor(ws_url, token, target, ttl_seconds, debounce_seconds):
    target_kind, _, target_id = target.partition(":")
    if target_kind not in ("group", "private"):
        sys.stderr.write("Error: --target must be 'group:<id>' or 'private:<id>'\n")
        sys.exit(1)

    # Version-adaptive headers: websockets >= 14 uses additional_headers, older uses extra_headers
    connect_kwargs = {}
    if token:
        params = inspect.signature(websockets.connect).parameters
        if "additional_headers" in params:
            connect_kwargs["additional_headers"] = {"Authorization": f"Bearer {token}"}
        else:
            connect_kwargs["extra_headers"] = {"Authorization": f"Bearer {token}"}

    start_time = time.time()
    deadline = start_time + ttl_seconds
    pending = []
    last_arrival = 0.0

    emit(MARKER_READY, target=target, ttl=ttl_seconds, debounce=debounce_seconds)

    while time.time() < deadline:
        try:
            async with websockets.connect(ws_url, **connect_kwargs) as ws:
                emit(MARKER_NOTICE, status="connected", target=target)
                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        raw = None
                    except Exception:
                        break  # Socket disconnected, outer loop reconnects

                    if raw:
                        try:
                            event = json.loads(raw)
                        except Exception:
                            event = {}

                        if event.get("post_type") == "message":
                            msg_type = event.get("message_type")
                            user_id = str(event.get("user_id", ""))
                            self_id = str(event.get("self_id", ""))

                            # Rule 2: Zero-guessing own identity
                            if user_id == self_id:
                                continue

                            # Match target conversation
                            is_target = False
                            if target_kind == "group" and msg_type == "group":
                                is_target = str(event.get("group_id", "")) == target_id
                            elif target_kind == "private" and msg_type == "private":
                                is_target = user_id == target_id

                            if is_target:
                                raw_text = event.get("raw_message", "")
                                sender_info = event.get("sender", {})
                                sender_name = sender_info.get("card") or sender_info.get("nickname") or user_id
                                pending.append({
                                    "user_id": user_id,
                                    "sender_name": sender_name,
                                    "text": raw_text,
                                    "time": event.get("time", int(time.time()))
                                })
                                last_arrival = time.time()

                    # Rule 3: 5.0s quiet-window debounce
                    if pending and (time.time() - last_arrival >= debounce_seconds):
                        emit(
                            MARKER_EVENT,
                            target=target,
                            messages=pending,
                            summary="\n".join([f"{p['sender_name']}: {p['text']}" for p in pending]),
                            count=len(pending),
                            timestamp=int(time.time())
                        )
                        pending.clear()

        except Exception as exc:
            emit(MARKER_NOTICE, status="reconnecting", error=str(exc))
            await asyncio.sleep(3)

    emit(MARKER_EXIT, reason="ttl_expired")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NapCat WS Takeover Sensor")
    parser.add_argument("--url", required=True, help="WebSocket URL (e.g. ws://127.0.0.1:3001)")
    parser.add_argument("--token", default="", help="Access Token")
    parser.add_argument("--target", required=True, help="Target conversation ('group:<id>' or 'private:<id>')")
    parser.add_argument("--ttl", type=int, default=1800, help="Max takeover duration in seconds")
    parser.add_argument("--debounce", type=float, default=5.0, help="Debounce silence window in seconds")

    args = parser.parse_args()
    asyncio.run(monitor(args.url, args.token, args.target, args.ttl, args.debounce))
```
