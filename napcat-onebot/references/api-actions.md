# Action Catalogue

Grouped by the task in front of you, not by the protocol's own sections. Every action is `POST {NAPCAT_API_URL}/<action>` with a JSON body of the listed parameters.

Verified on 2026-09-22 against NapCat's own API list (NapCat 4.18.28); the authorities behind that list, and the order to check them in, are in `sources.md`. NapCat extends OneBot 11 well beyond what is listed here. When a task needs something this page does not show, verify it against a source rather than guessing a plausible action name — a wrong name comes back as an unknown-action error, and the type definitions in the NapCatQQ repository are the last word on parameters.

## Table of contents

- Send a message
- Read messages
- Look things up
- Manage messages, groups and people
- Files and media
- Account
- What the HTTP surface cannot do

## Send a message

| Action | Parameters |
|---|---|
| `send_group_msg` | `group_id`, `message` |
| `send_private_msg` | `user_id`, `message` |
| `send_msg` | `message_type` (`group`/`private`), the matching `group_id`/`user_id`, `message` |
| `send_group_forward_msg` | `group_id`, `messages` (array of forward nodes) |
| `send_private_forward_msg` | `user_id`, `messages` |
| `send_poke` / `group_poke` / `friend_poke` | context-dependent; `group_poke` and `friend_poke` take `group_id`/`user_id` |
| `send_like` | `user_id`, `times` |

`message` is a string (CQ codes) or an array of segments — see `message-segments.md`.

## Read messages

| Action | Parameters | Returns |
|---|---|---|
| `get_group_msg_history` | `group_id`, `count` | recent messages in that group |
| `get_friend_msg_history` | `user_id`, `count` | recent private messages with that person |
| `get_recent_contact` | `count` | recent conversations (last message per peer, newest first) |
| `get_msg` | `message_id` | one message |
| `get_forward_msg` | `message_id` | the nodes inside a forwarded bundle |

Confirmed shapes (2026-09-22, NapCat 4.18.28, live calls):

- `get_group_msg_history` → `data.messages[]`, oldest first. Each entry carries `message_id`, `user_id`, `time`, a `sender` object (at least `nickname`), and `message` as a segment array.
- `get_recent_contact` → `data[]` with `peerUin`, `peerName`, `chatType` (`1` = private, `2` = group), `msgTime`, and `lastestMsg` (the spelling is NapCat's).

These four are what makes on-demand reading possible: pull the last N messages of a group or a person when a task needs context, instead of running a listener. When timing rather than content is the requirement, that is a different architecture — see `events-and-push.md`.

## Look things up

| Action | Parameters |
|---|---|
| `get_login_info` | — |
| `get_status` | — |
| `get_version_info` | — |
| `get_group_list` | optional `no_cache` |
| `get_group_info` | `group_id`, optional `no_cache` |
| `get_group_info_ex` | `group_id` |
| `get_group_member_list` | `group_id`, optional `no_cache` |
| `get_group_member_info` | `group_id`, `user_id`, optional `no_cache` |
| `get_friend_list` | optional `no_cache` |
| `get_friends_with_category` | — |
| `get_stranger_info` | `user_id`, optional `no_cache` |
| `get_unidirectional_friend_list` | — |
| `get_online_clients` | — |

`no_cache: true` forces a fresh read from QQ; it is slower and the right choice when a stale list would mislead.

## Manage messages, groups and people

| Action | Parameters |
|---|---|
| `delete_msg` | `message_id` |
| `mark_group_msg_as_read` | `group_id`, `time` |
| `mark_private_msg_as_read` | `user_id`, `time` |
| `mark_msg_as_read` | message-related |
| `set_group_ban` | `group_id`, `user_id`, `duration` (seconds, `0` lifts) |
| `set_group_whole_ban` | `group_id`, `enable` |
| `set_group_kick` | `group_id`, `user_id`, `reject_add_request` |
| `set_group_card` | `group_id`, `user_id`, `card` |
| `set_group_name` | `group_id`, `group_name` |
| `set_group_admin` | `group_id`, `user_id`, `enable` |
| `set_group_remark` | `group_id`, `remark` |
| `set_group_leave` | `group_id`, `is_dismiss` (owner only) |
| `set_friend_remark` | `user_id`, `remark` |
| `set_friend_add_request` | `flag`, `approve`, optional `remark` |
| `set_group_add_request` | `flag`, `approve`, optional `reason` |
| `_send_group_notice` | `group_id`, `content` |
| `_get_group_notice` | `group_id` |
| `set_essence_msg` / `delete_essence_msg` | `message_id` |
| `get_essence_msg_list` | `group_id` |
| `get_group_shut_list` | `group_id` |
| `get_group_at_all_remain` | `group_id` |

Actions prefixed with `_` or `.` are NapCat implementation details that are still callable; expect the prefix to change without notice and prefer an unprefixed alternative when one exists.

## Files and media

| Action | Parameters |
|---|---|
| `upload_group_file` | `group_id`, `file`, `name`, optional `folder` |
| `upload_private_file` | `user_id`, `file`, `name` |
| `get_group_root_files` / `get_group_files_by_folder` | `group_id` (+ `folder_id`) |
| `get_group_file_url` | `group_id`, `file_id`, `busid` |
| `delete_group_file` | `group_id`, `file_id`, `busid` |
| `download_file` | `url`, `thread_count`, `headers` |
| `get_image` | `file` |
| `get_record` | `file`, optional `out_format` |
| `get_file` | `file`, `type` |
| `ocr_image` | `image` |
| `can_send_image` / `can_send_record` | — |

`file` is resolved by the protocol side, on its own filesystem — see the sending-files section of `SKILL.md`.

## Account

| Action | Parameters |
|---|---|
| `set_self_longnick` | `longNick` |
| `set_online_status` | status codes, `ext_status`, `battery_status` |
| `set_diy_online_status` | `face_id`, `face_type`, `wording` |
| `set_qq_profile` | profile fields |
| `set_qq_avatar` | `file` |
| `get_cookies` / `get_credentials` | optional `domain` |
| `get_csrf_token`, `get_clientkey`, `get_rkey` | — |
| `set_input_status` | `user_id`, `event_type` |
| `_mark_all_as_read` | — |
| `clean_cache`, `bot_exit` | — |

`bot_exit` logs the account out. Never call it as a troubleshooting step.

## What the HTTP surface cannot do

- **Receive events.** The HTTP server is a single-direction (request/response) transport. Incoming messages are only pushed over reverse WebSocket or HTTP report — a listening process on your side. Reading history covers "what was said"; it does not cover "tell me the moment something is said". `events-and-push.md` covers the transports and what they cost.
- **Answer interactive elements** such as inline keyboard buttons, beyond the dedicated action for them (`click_inline_keyboard_button`).
- **Circumvent account limits.** Any QQ-side restriction (muted, kicked, rate-limited on the account) surfaces as a failing action, not as a protocol error you can work around.
