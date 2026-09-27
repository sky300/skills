# Chat Window Takeover (NapCat OneBot v11)

How an autonomous agent temporarily takes over a QQ private or group chat window to handle automated replies, without freezing the primary agent loop or polluting the user's primary chat session.

---

## 1. Core Architecture: Inversion of Control

### The Anti-Pattern
In standard tool-use execution, calling a long-running foreground tool (e.g. `while True: time.sleep(...)`) **blocks and suspends the primary agent model**. The agent cannot receive intermediate events, reason across turns, or formulate replies during tool execution. Doing so causes tool timeouts or completely stalls the conversation.

### The Decoupled Model (Sensor/Worker + Brain)
To allow an agent model to generate each chat reply dynamically, the architecture must separate:
1. **Event Sensor / Worker (Inbound)**: A non-blocking background listener that buffers, debounces, and filters incoming messages.
2. **Agent Reasoning (Brain)**: The agent receives the aggregated context in an isolated session turn, formulates a response, and returns the reply text.
3. **Outbound Dispatch**: The generated text is sent to the QQ conversation via OneBot HTTP API (`/send_private_msg` or `/send_group_msg`).

---

## 2. Architecture Selection: Preferred vs Fallback Decision Tree

Before opening a takeover window, the host agent must evaluate its platform capabilities:

### Tier 1: Preferred Architectures (Decoupled, Isolated & Silent)
Use Tier 1 whenever the host agent platform supports either an OpenAI-compatible API endpoint or a Webhook receiver. Both options keep the user-facing chat interface (e.g. Telegram, Discord, WebUI) completely clean and free of tool execution bubbles.

#### Option 1A: Worker + Agent API Server (Pull / WS + REST, Recommended)
- **Mechanism**: A lightweight background worker connects to NapCat's outbound WebSocket stream, applies 5-second silence debounce, and calls the agent platform's OpenAI-compatible API endpoint (e.g. `POST /v1/chat/completions` with a session routing header such as `X-Session-Id` or `X-Hermes-Session-Id`). The worker then posts the returned reply text to NapCat's HTTP API.
- **Why Recommended**:
  - **Zero NapCat Configuration Changes**: Operates over NapCat's default shared HTTP/WebSocket port without editing instance config files or restarting services.
  - **100% Silent & Non-Disruptive**: Runs on the platform's API server layer. Even if the user's chat client has verbose tool progress enabled (e.g. `tool_progress: all`), **zero tool bubbles or execution logs leak into the user's chat**.
  - **Context Isolation**: Chat history is kept in an independent session (e.g. `qq-group-<id>`), preventing QQ chatter from polluting the user's active prompt or consuming main session tokens.
  - **Full Agent Intelligence**: Retains the host agent's full system prompt, skills, and memory capabilities.

#### Option 1B: NapCat HTTP Report + Agent Webhook (Push + Event-Driven)
- **Mechanism**: If the agent platform supports dynamic Webhook subscriptions (e.g. `hermes webhook`, or custom HTTP callback endpoints), configure NapCat's `httpClients` to push message events directly to the Webhook URL. Each incoming webhook triggers an independent agent turn, which calls OneBot's HTTP API to reply.
- **Trade-off**: Completely event-driven without running a persistent background script, but requires modifying NapCat's instance configuration (`httpClients`) and restarting the service.

---

### Tier 2: Mandatory Fallback Negotiation Rule
> **Rule**: If the agent's host platform **does not** support an OpenAI-compatible API endpoint and **does not** support webhooks, the agent **must stop and discuss options with the user** before taking action. Never make a silent assumption or attempt proprietary hacks.

The agent must explain the trade-off and present the portable fallback:
- **Direct Model Gateway Worker (Standalone LLM Client)**:
  - The worker script bypasses the agent platform entirely and queries a bare external LLM API (e.g. OpenAI/Anthropic/DeepSeek endpoint or local vLLM/Ollama runner) directly.
  - *Warning to user*: The bot will reply completely silently without UI noise, but will lack the host agent's persistent memory, specialized skills, and local tool execution capabilities.

*(Note: In-session event injection via stdout pattern matching is avoided as a general recommendation because it relies on specialized runtime capabilities and is not portable across standard coding agents.)*

---

## 3. Resolving "Me" (Zero-Guessing Rule)

> **Rule**: When filtering out the account's own messages, **never guess the account identity** by inspecting friend lists, scanning remarks, or reading chat history.

In OneBot v11:
- **WebSocket Events**: Every event envelope natively contains `self_id` (the bot's UIN). Comparing `event.get("user_id") == event.get("self_id")` instantly identifies own-messages.
- **HTTP API**: Calling `GET /get_login_info` returns `{"data": {"user_id": <uin>, "nickname": "..."}}`.

Always rely strictly on these two authorities.

---

## 4. Recommended Design: 5-Second Silence Debounce

Human conversation patterns on instant messaging platforms rarely resemble single complete paragraphs. Users frequently split one thought across 2 to 4 rapid short messages within a few seconds.

### Why Debounce is Critical
1. **Semantic Completeness**: Merging rapid fragments (e.g. "Wait", "Actually", "Can you check this?") into a single prompt preserves full conversational context.
2. **Anti-Risk & Account Safety**: Instant, robotic replies to every single short line will trigger Tencent's platform risk controls and result in temporary muting or account restriction.
3. **Token & Call Efficiency**: Prevents spinning up 4 separate model completions when 1 coherent response is needed.

### Standard Debounce Policy
- **Default Window**: **5.0 seconds of silence**.
- The sensor resets its silence countdown on each new message from the target conversation. Once 5.0 seconds elapse with no further incoming messages, the aggregated buffer is emitted as a single event.

---

## 5. In-Flight Concurrency: What Happens if a New Message Arrives During Generation?

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

## 6. Enabling NapCat WebSocket Server

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

## 7. Daemon Execution & Lifecycle Management

How to run the background worker cleanly depends on the host agent's environment:

### Strategy 1: Agent-Native Background Runner (Recommended for Bounded/Temporary Takeover)
- If the host agent platform has a built-in background task runner (e.g. Hermes background terminal tool, Codex background execution):
  - Launch the worker directly via the agent's native background tool.
  - Rely on the worker's `--ttl` parameter for automatic self-termination once the requested duration expires.
  - **Advantage**: Zero host configuration footprint; leaves no dangling system files after the takeover window ends.

### Strategy 2: OS Service Fallback (Systemd User Unit / Launchd)
- If the agent tool lacks native background process management, or if the user requests **permanent/long-term unattended takeover**:
  - Run as an OS-level user daemon (e.g. Linux `systemd --user` service or macOS `launchd`).
  - Example systemd user unit (`~/.config/systemd/user/napcat-takeover.service`):
```ini
[Unit]
Description=NapCat OneBot Takeover Worker
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/uv run --with websockets python3 <path-to-worker.py> \
  --ws-url ws://<host>:<port> \
  --http-url http://<host>:<port> \
  --token <onebot_token> \
  --agent-api http://<agent-host>:<port>/v1/chat/completions \
  --agent-key <agent_key> \
  --target group:<target_group_id> \
  --debounce 5.0
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```
Manage cleanly with:
```bash
systemctl --user daemon-reload
systemctl --user start napcat-takeover.service
systemctl --user status napcat-takeover.service
```

---

## 8. Complete Production Worker Template (Option 1A)

This script acts as the background worker. It connects to the OneBot WebSocket, enforces 5.0s debounce, queries the Agent's OpenAI-compatible API endpoint in an isolated session, and sends replies via OneBot HTTP API.

Run seamlessly with `uv`:
```bash
uv run --with websockets python3 takeover_worker.py \
  --ws-url ws://127.0.0.1:3001 \
  --http-url http://127.0.0.1:3001 \
  --token <onebot_token> \
  --agent-api http://127.0.0.1:8642/v1/chat/completions \
  --agent-key <agent_key> \
  --target group:778330249 \
  --ttl 1800
```

### Script Code (`takeover_worker.py`)
```python
#!/usr/bin/env python3
"""
Production NapCat Takeover Worker (Preferred Architecture).
Listens to OneBot WS, debounces by 5s, calls Agent API Server, and dispatches reply.
Runs completely silent without polluting the user's primary chat session.
"""
import sys
import json
import time
import asyncio
import inspect
import argparse
import urllib.request
import urllib.error

try:
    import websockets
except ImportError:
    sys.stderr.write("Error: 'websockets' library required. Run with: uv run --with websockets python3 ...\n")
    sys.exit(1)

def query_agent_api(api_url, api_key, session_id, prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-Session-Id": session_id,
        "X-Hermes-Session-Id": session_id
    }
    payload = {
        "model": "default",
        "messages": [{"role": "user", "content": prompt}]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res["choices"][0]["message"]["content"].strip()
    except Exception as e:
        sys.stderr.write(f"Agent API call failed: {e}\n")
        return None

def send_onebot_message(http_url, token, target_kind, target_id, message_text):
    endpoint = "/send_group_msg" if target_kind == "group" else "/send_private_msg"
    url = f"{http_url.rstrip('/')}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {"message": message_text}
    if target_kind == "group":
        payload["group_id"] = int(target_id)
    else:
        payload["user_id"] = int(target_id)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"OneBot send failed: {e}\n")
        return None

async def run_worker(args):
    target_kind, _, target_id = args.target.partition(":")
    if target_kind not in ("group", "private"):
        sys.stderr.write("Error: --target must be 'group:<id>' or 'private:<id>'\n")
        sys.exit(1)

    connect_kwargs = {}
    if args.token:
        params = inspect.signature(websockets.connect).parameters
        if "additional_headers" in params:
            connect_kwargs["additional_headers"] = {"Authorization": f"Bearer {args.token}"}
        else:
            connect_kwargs["extra_headers"] = {"Authorization": f"Bearer {args.token}"}

    start_time = time.time()
    deadline = start_time + args.ttl
    pending = []
    last_arrival = 0.0

    print(f"Takeover Worker started for {args.target}, TTL={args.ttl}s", flush=True)

    while time.time() < deadline:
        try:
            async with websockets.connect(args.ws_url, **connect_kwargs) as ws:
                print("Connected to OneBot WebSocket stream.", flush=True)
                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        raw = None
                    except Exception:
                        break

                    if raw:
                        try:
                            event = json.loads(raw)
                        except Exception:
                            event = {}

                        if event.get("post_type") == "message":
                            user_id = str(event.get("user_id", ""))
                            self_id = str(event.get("self_id", ""))

                            # Rule: Zero-guessing own identity
                            if user_id == self_id:
                                continue

                            is_target = False
                            if target_kind == "group" and event.get("message_type") == "group":
                                is_target = str(event.get("group_id", "")) == target_id
                            elif target_kind == "private" and event.get("message_type") == "private":
                                is_target = user_id == target_id

                            if is_target:
                                raw_text = event.get("raw_message", "")
                                sender_info = event.get("sender", {})
                                sender_name = sender_info.get("card") or sender_info.get("nickname") or user_id
                                pending.append(f"{sender_name}: {raw_text}")
                                last_arrival = time.time()

                    # 5.0s Debounce trigger
                    if pending and (time.time() - last_arrival >= args.debounce):
                        aggregated_text = "\n".join(pending)
                        pending.clear()

                        prompt = (
                            f"The following message(s) arrived in the conversation ({args.target}):\n"
                            f"{aggregated_text}\n\n"
                            f"Reply naturally as a regular chat participant. Output only the message text directly."
                        )
                        session_id = f"qq-{target_kind}-{target_id}"
                        reply = await asyncio.to_thread(
                            query_agent_api, args.agent_api, args.agent_key, session_id, prompt
                        )
                        if reply:
                            # Pacing delay
                            await asyncio.sleep(2.0)
                            await asyncio.to_thread(
                                send_onebot_message, args.http_url, args.token, target_kind, target_id, reply
                            )

        except Exception as exc:
            print(f"Connection error: {exc}. Retrying in 3s...", flush=True)
            await asyncio.sleep(3)

    print("Takeover Worker TTL expired.", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NapCat Takeover Worker")
    parser.add_argument("--ws-url", required=True, help="OneBot WebSocket URL")
    parser.add_argument("--http-url", required=True, help="OneBot HTTP API URL")
    parser.add_argument("--token", default="", help="OneBot Token")
    parser.add_argument("--agent-api", required=True, help="Agent Platform OpenAI-compatible API URL")
    parser.add_argument("--agent-key", default="", help="Agent Platform API Key")
    parser.add_argument("--target", required=True, help="Target conversation ('group:<id>' or 'private:<id>')")
    parser.add_argument("--ttl", type=int, default=1800, help="TTL in seconds")
    parser.add_argument("--debounce", type=float, default=5.0, help="Debounce in seconds")

    args = parser.parse_args()
    asyncio.run(run_worker(args))
```
