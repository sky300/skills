# Chat Window Takeover (NapCat OneBot v11)

How an autonomous agent temporarily takes over a QQ private or group chat window to handle automated replies, without freezing the primary agent loop.

## Core Architecture: Inversion of Control

### The Anti-Pattern
In standard tool-use execution, calling a long-running foreground tool (e.g. `while True: time.sleep(...)`) **blocks and suspends the primary agent model**. The agent cannot receive intermediate events, reason across turns, or formulate replies during tool execution. Doing so causes tool timeouts or completely stalls the conversation.

### The Decoupled Model
To allow the **current session's primary model** to generate each chat reply dynamically, the architecture must separate:
1. **Event Sensor (Inbound)**: A non-blocking background listener or webhook receiver that buffers and filters messages.
2. **Agent Trigger (Interrupt)**: An out-of-band notification or webhook callback that wakes the primary model for a single reasoning turn.
3. **Agent Action (Outbound)**: The model reasons over context, drafts the response, and calls `send_private_msg` / `send_group_msg` via HTTP.

---

## Two Feasible Approaches

### Approach 1: NapCat HTTP Report + Agent Webhook (Event-Driven)
NapCat pushes message events via HTTP POST to the agent platform's webhook endpoint (e.g. `hermes webhook`).

1. **Register Subscription**: The agent registers a temporary webhook listener (e.g. `hermes webhook subscribe qq-takeover ...`).
2. **Dispatch**: NapCat forwards incoming messages to the webhook URL.
3. **Model Wakeup**: The platform receives the POST, formats the prompt with the sender and text, and invokes a single agent turn.
4. **Execution**: The model reasons, calls the OneBot HTTP API to reply, and finishes the turn.
5. **Teardown**: When the takeover duration expires, the agent removes the webhook subscription.

### Approach 2: Background WS Sensor + Pattern-Match Notification (Self-Contained)
A lightweight background Python script monitors NapCat's WebSocket stream, while the agent runtime intercepts trigger patterns from its stdout.

1. **Launch Sensor**: The agent launches the sensor in the background:
   `terminal(command="python3 takeover_sensor.py ...", background=true, notify=["NEW_MESSAGE:*"])`
2. **Debounce & Filter**:
   - The script connects to NapCat's forward WebSocket.
   - Buffers incoming lines from the target UIN across a 3–5 second window (combining rapid multi-line messages).
   - Ignores self-sent messages (`sender.user_id == self_id`).
   - If the account owner sends a message from another client (e.g. phone), the script terminates immediately to surrender control.
3. **Interrupt & Wake**: When ready, the script prints:
   `NEW_MESSAGE: {"user_id": 123456, "text": "combined message"}`
   The runtime's process manager catches the pattern and injects it as an out-of-band message into the active conversation turn.
4. **Model Reply**: The model wakes up, sees `NEW_MESSAGE: ...`, generates a reply, and calls `send_private_msg`.
5. **Teardown**: The sensor self-terminates when its TTL expires, or the agent terminates it via process management tools.

---

## Enabling NapCat WebSocket Server

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

## Python Sensor Template (Approach 2)

This template serves as a background event sensor. It computes only what must be exact (event parsing, debouncing, interruption checks) and does not call any LLM directly.

```python
#!/usr/bin/env python3
"""
Lightweight NapCat OneBot v11 WebSocket Sensor.
Connects to NapCat WS, debounces target messages, checks for owner takeover,
and outputs 'NEW_MESSAGE: <json>' to stdout for runtime pattern matching.
"""
import sys
import json
import time
import asyncio
import argparse

try:
    import websockets
except ImportError:
    sys.stderr.write("Error: 'websockets' library is required (pip install websockets).\n")
    sys.exit(1)

async def monitor(ws_url, token, target_uin, self_uin, ttl_seconds, debounce_seconds):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    start_time = time.time()
    last_msg_time = 0
    buffer = []

    async with websockets.connect(ws_url, extra_headers=headers) as ws:
        while (time.time() - start_time) < ttl_seconds:
            try:
                # Wait for next frame with timeout to handle debounce flushes
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                event = json.loads(raw)
            except asyncio.TimeoutError:
                # Flush buffer if silence window elapsed
                if buffer and (time.time() - last_msg_time >= debounce_seconds):
                    payload = {"user_id": target_uin, "text": "\n".join(buffer)}
                    print(f"NEW_MESSAGE: {json.dumps(payload, ensure_ascii=False)}", flush=True)
                    buffer.clear()
                continue

            if event.get("post_type") != "message":
                continue

            sender_id = str(event.get("user_id") or event.get("sender", {}).get("user_id"))

            # Owner interruption detection: owner spoke in the chat
            if sender_id == str(self_uin):
                sys.stderr.write("Owner active in target chat. Surrendering takeover.\n")
                sys.exit(0)

            # Match target conversation
            if sender_id == str(target_uin):
                raw_text = event.get("raw_message", "")
                buffer.append(raw_text)
                last_msg_time = time.time()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NapCat WS Takeover Sensor")
    parser.add_argument("--url", required=True, help="WebSocket URL (e.g. ws://127.0.0.1:3001)")
    parser.add_argument("--token", default="", help="Access Token")
    parser.add_argument("--target", required=True, help="Target UIN")
    parser.add_argument("--self-uin", required=True, help="Bot's own UIN")
    parser.add_argument("--ttl", type=int, default=3600, help="Max takeover duration in seconds")
    parser.add_argument("--debounce", type=float, default=3.5, help="Debounce window in seconds")

    args = parser.parse_args()
    asyncio.run(monitor(args.url, args.token, args.target, args.self_uin, args.ttl, args.debounce))
```

---

## Safety and Pacing Guidelines

1. **Debounce (Message Aggregation)**:
   Human chat patterns involve splitting one sentence across 2–4 rapid messages. The sensor buffers lines over 3–5 seconds before waking the agent.
2. **Anti-Loop Defense**:
   Filter out messages where `sender.user_id` matches the bot's own account.
3. **Owner Preemption**:
   If the user opens their phone and sends a message in the same chat, the agent must surrender control immediately.
4. **Pacing**:
   Add a randomized typing delay (3–8 seconds) before calling `send_private_msg` to avoid robotic instant responses that trigger platform risk control.
