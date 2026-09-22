# Events and Push

Incoming messages are not something the HTTP request/response surface can deliver: one call, one answer, no stream. This page covers what the alternatives are, so a task that needs live messages is recognised as a different architecture rather than attempted through the wrong one.

**Status of these notes:** the transport names, configuration keys and their semantics come from NapCat's WebUI configuration documentation (checked 2026-09-22, NapCat 4.18.28). The wiring advice below is design reasoning, not something tested with this skill — treat it as a plan to validate, not as a verified recipe.

## The three transports

| Transport | Direction | Configuration key | Meaning |
|---|---|---|---|
| HTTP server | inbound calls | `httpServers` | You call in: actions. This is what the rest of this skill uses. No events. |
| WebSocket server (forward WS) | both | `websocketServers` | You connect out to the protocol side and receive events on a socket you opened. |
| WebSocket client (reverse WS) | both | `websocketClients` | The protocol side connects out to a URL you listen on. Survives the protocol side restarting behind NAT, which is why bot frameworks usually prefer it. |
| HTTP client (HTTP report) | outbound events | `httpClients` | The protocol side POSTs each event to a URL you listen on. Simplest to receive, and the only one that works if your side cannot hold a socket open. |

Relevant options on the event-pushing entries (`httpClients`, `websocketClients`):

- `messagePostFormat` — `array` or `string`: whether the message body arrives as segments or as a CQ-code string. Pick `array` for the same reason sends use it.
- `reportSelfMessage` — whether the account's own messages are reported too. Leaving it off keeps "new message" meaning "someone else spoke"; turning it on means every reply you send comes back as an event and must be filtered, or it will loop.
- `token` — must be the same value on both sides; the protocol side authenticates with it.
- `reconnectInterval`, `heartInterval` — the client transports reconnect on their own schedule and heartbeat to detect a dead link.

## What adding live events actually costs

- **A process that is always up.** Events are pushed at whatever moment they happen; something has to be listening then. An agent that is only running when a human asks it something cannot receive them.
- **Reconnect and backlog handling.** Sockets drop — the protocol side restarts, the network moves. Whatever receives events must reconnect and decide what to do about messages that arrived while it was down.
- **A decision about what to do with them.** Being woken is not the goal; the goal is a reaction. That means a queue, a debounce (one burst of messages from one person is one interruption, not five), and a rule for when not to answer at all.
- **Filtering your own messages** whenever `reportSelfMessage` is on, or a reply triggers a reply.

## When reading history is enough

Pull-based reading (`get_group_msg_history`, `get_friend_msg_history`, `get_recent_contact`) covers every case where the question is "what was said?", "what did I miss?", "summarise the last 200 messages", or "reply to the thread about X". It needs no listener, no queue and no always-on process, and it degrades gracefully: if the call fails, nothing is lost, because nothing was streaming.

Reach for push only when the *timing* is the requirement — being woken by a message rather than asking about it.

## Bringing it up

If a task does need push, the shape is: add a transport entry on the protocol side (WebUI network configuration, or the JSON config file it writes), stand up a listener on the agreed URL and port, and verify in this order — the listener is reachable, the protocol side reports a connected client, one real incoming message arrives, and only then anything acts on it. Test with a message from another account to yourself, so the first event you receive is not also the thing you want to react to.
