# Requests and Errors

Verified on 2026-09-22 against NapCat 4.18.28 (OneBot 11 over HTTP); every claim below about the envelope and the failure modes was reproduced against a live instance. The authorities behind them are listed in `sources.md`. OneBot 11 itself is a stable published standard — <https://github.com/botuniverse/onebot-11> — so the envelope is not NapCat-specific, while the failure notes are drawn from NapCat's behaviour.

## The request

```bash
curl -sS -X POST "$NAPCAT_API_URL/send_group_msg" \
  -H "Authorization: Bearer $NAPCAT_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"group_id": "123456789", "message": [{"type": "text", "data": {"text": "hi"}}]}'
```

- Path is the action name. The base URL must not carry a trailing slash.
- Body is a single JSON object; parameterless actions take `{}`.
- `Authorization: Bearer <token>` — the header name and the `Bearer ` prefix are both required. A token configured as empty means no header is needed; do not send `Bearer ` with nothing after it.
- `POST` for everything. `GET` with query parameters is accepted for parameterless actions and is convenient in a browser; it is not the form to build on.

## The response

```json
{"status": "ok", "retcode": 0, "data": {"user_id": 10001, "nickname": "..."},
 "message": "", "wording": "", "echo": "pbfb9esojcm", "stream": "normal-action"}
```

- `status` is `ok` or `failed`; `retcode` is `0` on success. Judge on both.
- `data` holds the payload; its shape is per-action and documented per-action (`api-actions.md`).
- `message` carries the failure text when `status` is `failed`; `wording` is a human-facing hint and may be empty.
- `echo` is **not** an echo of your request unless you sent one — NapCat fills in a random value when the caller omits it, so its presence tells you nothing about what you asked. Send your own `echo` when you pipeline calls and need to match replies to requests.
- The HTTP status is not the verdict: a rejected action usually still answers `200` with `status: "failed"`.

## Failures and what they mean

| Symptom | Cause | What to do |
|---|---|---|
| HTTP 403 with `{"message": "token verify failed!"}` | `NAPCAT_ACCESS_TOKEN` does not match the server's configured token | Ask the user for the current token; do not retry in a loop |
| Connection reset / refused while the port is open, on **every** action | The protocol side has not completed (or has lost) its QQ login. NapCat starts serving HTTP only once the account is up | Report it; the fix is a QR login on the protocol side, not a code change |
| Connection refused, nothing listening | Wrong port or base URL, or the container is down | Confirm `NAPCAT_API_URL` with the user and check the protocol side is running |
| `status: "failed"`, `retcode` non-zero | Action-level rejection: unknown action, missing or malformed parameter, account cannot do this here (not a member, muted, no permission) | Read the `message` field and fix the request; retrying identically will fail identically |
| `data` empty when you expected a list | The action succeeded but there is nothing to return (no such group, empty history, no permission cache) | Treat as a real answer, not an error |
| An id arrives with the last digits wrong | JSON number precision loss in whatever consumed the reply | Re-read with the id kept as a string, and pass ids on as strings |

## Ids

`group_id`, `user_id` and `message_id` are numeric, but every action accepts them as strings and some `message_id` values exceed what a consumer that parses JSON numbers into doubles represents exactly. Keep ids as strings both when sending them and when echoing them back; if a value you already have as a number looks truncated, fetch it again rather than repairing digits.

## Timeouts and retries

There is no request idempotency: a send that times out after the server accepted it **has been sent**. Retrying a `send_*` on timeout therefore risks a duplicate message. When a send times out, verify with history (`get_group_msg_history`, `get_friend_msg_history`) before deciding, and prefer asking the user how to proceed over guessing.
