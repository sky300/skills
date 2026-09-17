# Runtime Identity

Use this file when a rootless deployment hits bind-mount permission problems, or when the source image declares a fixed runtime user that differs from the host user. It covers UID/GID mapping semantics, the diagnostic path, and when `UserNS=` mapping is the right fix.

## Contents

- Default posture
- When identity mapping is needed
- `UserNS=keep-id` semantics
- Diagnostic path
- Host-side ACL alternative
- Common mistakes

## Default posture

Do not add `User=`, `Group=`, or `UserNS=` speculatively. Under rootless Podman, a container whose image default user matches the host UID already works; adding identity directives without a diagnosed mismatch changes behavior and makes the output harder to reason about.

Add identity mapping only after the diagnostic path below confirms an ownership mismatch between the container runtime user and the mounted host path.

## When identity mapping is needed

Two symptoms indicate a UID/GID mismatch between the container user and the host:

- the container cannot read or write a bind-mounted host path that the host user owns (typical when the image runs as a fixed non-zero UID and the host path has restrictive permission bits)
- the container writes files into the mount that the host user cannot read or manage (files appear owned by an unrelated host UID, typically a subordinate UID in the `/etc/subuid` range)

Both symptoms share one root cause: the image's declared runtime UID does not map to the host user. Named volumes avoid this problem because Podman initializes them with the container user's ownership — but switching a bind mount to a named volume changes the storage model and is a finalize-level decision, not a permission workaround.

## `UserNS=keep-id` semantics

Plain `UserNS=keep-id` maps the host user onto the container's default user. It only holds when the image's default user matches the runtime user the service actually uses.

The parameterized form maps the host user onto an explicit container UID:

```ini
[Container]
UserNS=keep-id:uid=<container_uid>,gid=<container_gid>
```

- `<container_uid>` / `<container_gid>`: the UID/GID the service runs as inside the image
- effect: inside the container, the image's runtime user is backed by the host user's identity, so it receives the host user's permissions on bind mounts
- files the container writes into the mount are owned by the host user on the host side

Use the parameterized form whenever the image declares a fixed non-zero runtime user. Verify the image's runtime UID/GID before writing the value (see diagnostic path) instead of guessing from the service name.

## Diagnostic path

1. Confirm it is a permission-bit problem, not a path or mount problem: compare numeric ownership on both sides.

   ```bash
   podman exec <container> ls -ln <mounted-path>
   ls -ln <host-path>
   ```

   If the UIDs differ, continue. If the path is missing or the mount is absent, fix that first.

2. Read the container's UID mapping to see how container UIDs map back to the host:

   ```bash
   podman exec <container> cat /proc/self/uid_map
   ```

   Under rootless Podman, the container's non-zero users map into the host's subordinate UID range (`/etc/subuid`), which has no access to host files owned by the user.

3. Determine the image's declared runtime user:

   ```bash
   podman run --rm <image> id
   ```

   or read the last `USER` directive in the image's Containerfile / upstream docs.

4. Verify the mapping with a throwaway run before touching the Quadlet:

   ```bash
   podman run --rm --userns keep-id:uid=<container_uid>,gid=<container_gid> \
     -v <host-path>:<mounted-path> <image> id
   ```

   Then check the mount point is readable/writable inside that run.

5. Only after the dry run succeeds, write `UserNS=keep-id:uid=<container_uid>,gid=<container_gid>` into the `[Container]` section.

## Host-side ACL alternative

When the default user namespace should be preserved — for example several containers with different runtime UIDs share one host path, or the user prefers not to change namespace semantics — grant the mapped host UID access on the host instead:

```bash
setfacl -m u:<mapped_host_uid>:rx <host-path>
```

Use `rwx` when the container must write. The mapped host UID for a container user is the value observed in step 2 of the diagnostic path.

## Common mistakes

- Mount flags do not fix permission-bit denials. `:ro` restricts access, `:Z`/`:z` only relabel SELinux, and `idmap` changes how ownership is translated but does not by itself reconcile a fixed container UID with the host user.
- Adding plain `UserNS=keep-id` for an image whose default user is `root` or a mismatched UID silently keeps the problem.
- Mapping `uid=` to a value other than the image's declared runtime user leaves the service running as an identity that no longer matches the mount ownership.
- Debugging mounts when the real issue is identity: if `podman exec` can access the path but the service cannot, compare the service process UID (`podman exec <container> id`) against the mount ownership before touching `Volume=` lines.
