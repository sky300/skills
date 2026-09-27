# Device Identity and Login Persistence (NapCat)

How to ensure a persisted QQ login survives container recreation or service restarts without repeated QR code scans, and why the device identity mechanism matters.

---

## The Login Chain

When running NapCat in a container or headless environment (e.g. `mlikiowa/napcat-docker`), login restoration follows a strict sequence:

1. **Core Quick Login via CLI Flag**:
   The entrypoint script branches on the `ACCOUNT` environment variable:
   - **`ACCOUNT` is set**: runs `qq --no-sandbox -q "$ACCOUNT"`. NapCat Core inspects previous sessions in the local data directory and attempts a fast ticket-based login.
   - **`ACCOUNT` is unset**: runs `qq --no-sandbox`. NapCat logs `没有 -q 指令指定快速登录，将使用二维码登录方式` and displays a QR code.
2. **WebUI Proxy & Password Fallback**:
   The WebUI backend runs alongside the core and checks `NAPCAT_QUICK_ACCOUNT` (or `webui.json`'s `autoLoginAccount`). If the initial ticket has expired, it attempts automated password-based fallback login using `NAPCAT_QUICK_PASSWORD` or `NAPCAT_QUICK_PASSWORD_MD5`.
3. **Device GUID Verification**:
   The QQ authentication server validates the session ticket against the hardware fingerprint (Device GUID). If the GUID changes, the server invalidates the stored ticket and demands a fresh scan or device verification.

---

## The Four Login Variables

| Variable | Role |
| :--- | :--- |
| `ACCOUNT` | Passed to QQ command line as `-q <uin>`. Required for the core to even attempt quick login at startup. |
| `NAPCAT_QUICK_ACCOUNT` | Specifies the UIN for WebUI auto-login and delays early QR code output. |
| `NAPCAT_QUICK_PASSWORD` | Plaintext QQ password used for automated password fallback when ticket expires. |
| `NAPCAT_QUICK_PASSWORD_MD5` | 32-character lowercase MD5 hex of the password (alternative to plaintext). |

### Set All Four
These variables are **complementary, not mutually exclusive**. `ACCOUNT` triggers the ticket reuse attempt on boot; the password variables handle ticket expiration gracefully without human intervention.

A normal self-healing restart log looks like:
```text
正在快速登录  <uin>
快速登录错误： 登录态已失效，请重新登录。
正在尝试密码回退登录  <uin>
正在密码登录  <uin>
密码回退登录成功  <uin>
```
Seeing `登录态已失效` on the first stage is expected behavior when a ticket ages out. The password fallback stage transparently re-establishes the session.

---

## Linux Device GUID & Network MAC Binding

### The Underlying Algorithm
In Linux NTQQ, the device identifier is derived from:
$$\text{GUID} = \text{MD5}( \text{/etc/machine-id} + \text{MAC Address} )$$
- The MAC address format is `xx-xx-xx-xx-xx-xx` (lowercase, hyphens).
- The identity file is located at `<QQ_DATA_DIR>/nt_qq/global/nt_data/msf/machine-info`.
- Inside `machine-info`, the MAC address is stored as `[4-byte big-endian length N] [N-byte ROT13-encoded MAC string]`.

### The Container Recreation Pitfall
By default, Docker/Podman generates a random MAC address when creating a container network interface (bridge/veth).
- Recreating a container assigns a **new MAC address**.
- NTQQ calculates a **new GUID**.
- The QQ server treats the container as an unknown new device and invalidates existing session tickets.

### How to Fix
1. **Pin the Container MAC Address**:
   - In Docker Compose: specify `mac_address: "02:42:ac:11:00:02"`.
   - In `docker run`: pass `--mac-address "02:42:ac:11:00:02"`.
   - In Podman Quadlet (`.container`): pass `PodmanArgs=--mac-address=02:42:ac:11:00:02` (in bridge mode) or keep network namespaces persistent.
2. **WebUI Device GUID Management**:
   The NapCat WebUI provides a **Device GUID Management** panel (`设备 GUID 管理`). If the container network cannot be fixed, the recorded MAC or GUID can be manually aligned or backed up via the WebUI API.

---

## Required Persistent Volumes

Headless NapCat requires exactly two persistent directory mounts:

| Container Path | Purpose |
| :--- | :--- |
| `/app/.config/QQ` | Stores session tokens, tickets, SQLite databases (`nt_msg.db`), and device identity (`nt_qq/global/nt_data/msf/machine-info`). |
| `/app/napcat/config` | Stores WebUI token configuration (`webui.json`) and per-UIN OneBot network configurations (`onebot11_<uin>.json`). |

Ensure file permissions allow the container user (controlled by `NAPCAT_UID` / `NAPCAT_GID`, default `0`) full read and write access to both host directories.

---

## Symptom Triage

1. **Shows QR code on every container restart, `ACCOUNT` not set**:
   Set `ACCOUNT=<uin>` in the container environment.
2. **Shows QR code on every container restart, `ACCOUNT` is set**:
   The container MAC address or `/etc/machine-id` changed during recreation, altering the GUID. Pin the container MAC address.
3. **Quick login fails but password fallback succeeds**:
   Normal ticket aging. No action required; the session is successfully restored.
4. **Frequent disconnects / kicked offline after several hours**:
   Account-level risk control by the platform, not a volume or configuration fault. Ensure NapCat and the underlying QQ binary are updated to latest versions.
