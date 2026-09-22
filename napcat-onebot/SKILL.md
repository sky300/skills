---
name: napcat-onebot
description: "Use when sending or reading QQ messages through a NapCat OneBot v11 HTTP API: group and private messages, chat history, groups, friends, files."
---

# NapCat OneBot HTTP API

Talk to QQ through a self-hosted [NapCat](https://github.com/NapNeko/NapCatQQ) protocol side that exposes [OneBot 11](https://github.com/botuniverse/onebot-11) over HTTP. Use it to send group and private messages and to read chat history on demand.

This skill covers the **HTTP request/response surface** — calls the agent makes itself. It does not cover event push (reverse WebSocket, HTTP report): the HTTP server cannot wake you when someone sends a message. Read history on demand instead of building a listener unless the task really requires live reactions.

## Credentials

Two values, both supplied by the user's environment:

- `NAPCAT_API_URL` — base URL of the OneBot HTTP server, no trailing slash. The host and port are whatever the deployment exposes, so take them from the user instead of assuming a default.
- `NAPCAT_ACCESS_TOKEN` — the token configured on that server

If either is missing, ask the user. Do not guess a port, and do not recycle a token out of another tool's config file.

## Verify before you send

Call `get_login_info` first and read the returned account. A send action against a protocol side that is not logged in fails in ways that look like a scripting bug but are an account problem.

If every call fails with a connection reset or refused, while the port itself is open, the usual cause is that the protocol side has not finished (or has lost) its QQ login: the OneBot HTTP server only serves requests after a successful login. Report that to the user instead of retrying.

## Calling an action

```bash
curl -sS -X POST "$NAPCAT_API_URL/get_login_info" \
  -H "Authorization: Bearer $NAPCAT_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' -d '{}'
```

- The action name is the URL path: `{NAPCAT_API_URL}/<action>`.
- Parameters are a JSON object in the body. An empty object is fine for parameterless actions.
- `GET` with query parameters also works for parameterless actions; `POST` is the canonical form and the one to use.
- Response envelope:

```json
{"status": "ok", "retcode": 0, "data": {...}, "echo": "optional"}
```

Treat `status == "ok"` **and** `retcode == 0` as success; anything else is a failure. Surface the `retcode` and `message` rather than retrying blindly — most non-zero codes are permanent for that request (the account cannot post there, the id does not exist, the token is wrong).

## Actions you will reach for

Send:

- `send_group_msg` — `group_id`, `message`
- `send_private_msg` — `user_id`, `message`
- `send_msg` — `message_type` (`group`/`private`) plus the matching id

Read:

- `get_group_msg_history` — `group_id`, `count`
- `get_friend_msg_history` — `user_id`, `count`
- `get_recent_contact` — `count` (recent conversations, newest first)
- `get_msg` — `message_id`

Look up:

- `get_group_list`, `get_group_info`, `get_group_member_list`, `get_group_member_info`
- `get_friend_list`, `get_stranger_info`, `get_login_info`, `get_status`

Manage:

- `delete_msg` (`message_id`), `mark_group_msg_as_read` / `mark_private_msg_as_read`
- `set_group_ban`, `set_group_kick`, `set_group_card`, `group_poke` / `friend_poke`, `send_like`

Files and media:

- `upload_group_file` / `upload_private_file` — `group_id`/`user_id`, `file`, `name`
- `get_image`, `get_record`, `get_file`, `ocr_image`

The full catalogue by task is in `references/api-actions.md`.

## Message content

`message` accepts either a CQ-code string or an array of message segments. **Prefer the array form**: it survives text that contains `[` `]` `&`, needs no escaping, and is what the protocol side reports back.

```json
[
  {"type": "text", "data": {"text": "deploy finished"}},
  {"type": "at", "data": {"qq": "10001"}},
  {"type": "image", "data": {"file": "https://example.com/chart.png"}}
]
```

Segment types and their fields: `references/message-segments.md`.

Ids (group, user, message) are numeric but every parameter accepts a string. When an id or a message id comes back to you as a JSON number, keep it as a string when you pass it on — QQ's message ids can exceed the range a JavaScript-based consumer represents exactly.

## Sending files and images

The protocol side resolves `file` on **its own filesystem**, not on the machine you are calling from. A path that exists locally is meaningless to it when NapCat runs in a container or on another host.

- Prefer an `http(s)` URL the protocol side can fetch.
- `base64://...` also works and needs no shared filesystem.
- A `file://` path only works if that same path exists inside the protocol side's runtime — verify before assuming it.

## Pacing and account risk

The protocol side does not throttle you; QQ's own risk control does, and it acts on the account, not the process.

- Send at human pace. Bulk or broadcast sending to people who did not ask for it is the pattern that gets a personal account restricted.
- Prefer one useful message over a burst; when several messages are needed, compose one message with several segments.
- Ask the user before any send that goes to a group or person the user did not name in this request. Reads are free; sends are outward-facing and irreversible.

## Running the protocol side

If no NapCat instance answers at `NAPCAT_API_URL`, one has to exist before this skill is useful. The pieces, in order — install steps belong to the agent doing the deployment, adapted to that host's container runtime:

1. Run the NapCat container image published by the project (Docker Hub `mlikiowa/napcat-docker`), with a persistent directory for the QQ data and another for NapCat's own config, and both the WebUI port and the OneBot HTTP port published.
2. The image's entrypoint expects to start as root (it adjusts the internal user and then drops privileges), so on rootless Podman keep the container root and set the uid/gid environment variables to `0`, and do **not** add a `keep-id` user namespace — it demotes the entrypoint and every preparation step fails.
3. Open the WebUI and complete QR login; the login token is printed in the container log and lives in the WebUI config file. The login is persisted in the QQ data directory, so a restart does not need a new scan.
4. In the WebUI's network configuration, add an **HTTP server** entry: a port and a token. That port is `NAPCAT_API_URL`; that token is `NAPCAT_ACCESS_TOKEN`.
5. Confirm with `get_login_info` before declaring it done.

A personal QQ account driven through a protocol side violates QQ's terms of service and can be restricted or banned. Say so plainly before deploying, and never deploy one on an account the user would miss.

## References

- `references/sources.md` — every authority this skill rests on, what each covers, and the order to check them in
- `references/api-actions.md` — actions grouped by task, with parameters, and what the HTTP surface cannot do
- `references/request-and-errors.md` — envelope, authentication failures, retcode handling, id precision
- `references/message-segments.md` — segment types, fields, and what arrives back in history
- `references/events-and-push.md` — the push transports to reach for when timing, not content, is the requirement
