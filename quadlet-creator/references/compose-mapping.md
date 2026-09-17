# Compose Mapping

Use this file when converting `docker-compose.yml` or `compose.yaml` into Quadlet units.

## Contents

- General defaults
- Field mapping
- Topology guidance
- Risky or lossy areas

## General Defaults

- Model each service first, then decide how to group the result into one or more `.pod` units.
- Prefer maintainable Quadlet output over mechanical one-to-one translation.
- Keep filenames stable and predictable. Use a shared project prefix for generated artifacts.
- Do not add explicit runtime naming directives such as `PodName=`, `ServiceName=`, `ContainerName=`, or `NetworkName=` by default. Let Quadlet and Podman derive runtime names unless the user explicitly asks for custom naming or a reviewed requirement depends on it.
- Do not add `User=`, `Group=`, or `UserNS=keep-id` by default. Preserve or introduce runtime identity mapping only when the source explicitly requires it or when the user is working through permission or ownership behavior.
- For env-specific decisions, use `references/env-strategy.md` instead of expanding the env rules here.

## Field Mapping

### `name`

- Use it as an application prefix when it improves naming clarity.
- Do not force a top-level project name into every filename if the user prefers shorter units.

### `services.<name>.image`

- Map to `Image=` in `[Container]`.
- Prefer fully qualified image names when normalizing output.
- If the source omits a registry and is using Docker Hub semantics, normalize it explicitly for Podman.
- Use these rules when filling in Docker Hub references:
  - `redis:7` -> `docker.io/library/redis:7`
  - `nginx` -> `docker.io/library/nginx`
  - `examplecorp/api:latest` -> `docker.io/examplecorp/api:latest`
- Do not guess `docker.io/library/...` for images that already include a namespace.

### `services.<name>.build`

- Prefer upstream published images over local builds when the project already documents supported registry images.
- If the user wants declarative builds, create a `.build` unit and reference it from `Image=`.
- If the build semantics are too custom, or if an equivalent upstream image is clearly available, keep this as a manual follow-up item instead of guessing.

### `container_name`

- Drop it.
- Do not generate `ContainerName=`.

### `ports`

- For a standalone service, map to `PublishPort=` on the `.container`.
- For a pod-based topology, prefer `PublishPort=` on the `.pod` when the published ports belong to the pod boundary rather than one child container.
- When `PublishPort=` maps a host-side port, detect whether that host port is already in use before finalizing the mapping. Check for TCP/UDP listeners on the host using an available port-detection method. If a conflict is found, stop and ask the user whether to change the host port, skip the mapping, or resolve the conflict manually. Do not silently remap occupied host ports to an alternative.

### `volumes`

- Bind mounts become `Volume=HOST:CONTAINER[:OPTIONS]`.
- Normalize relative host paths against the Compose file directory and emit absolute paths in the final Quadlet output.
- Preserve bind-mount shape from the source input: a file bind mount must stay a file bind mount, and a directory bind mount must stay a directory bind mount.
- Do not widen a file mount into a directory mount, or collapse a directory mount into a file mount, unless the source is genuinely ambiguous or the upstream deployment docs explicitly require a different reviewed mapping.
- Named volumes can remain referenced by name, but when the user wants explicit infrastructure-as-code, create matching `.volume` units.
- Ask the user which volume mode they want when the source does not make the intended persistence model obvious.
- If a bind mount points to a repo-local file or directory, include that source in the reviewable deliverable set unless the user explicitly wants a host-managed external path instead.
- If a bind mount references a whole directory, inspect and preserve the required directory contents rather than only naming the directory root.

### `networks`

- Prefer pod-first topology over preserving Compose bridge networks mechanically.
- If the source uses a default network only, you often do not need a `.network` unit at all.
- If the source uses bridge networking for containers that can reasonably live in one pod, collapse that topology into one `.pod` so the containers share one network namespace.
- Create a `.network` unit only when services must be split across pods, or when explicit network isolation or custom network management is materially required.
- Do not add `NetworkName=` by default.
- Containers in the same `.pod` can communicate over `127.0.0.1` / `localhost` because they share a network namespace.
- When services in the same `.pod` must accept connections from sibling containers, ensure they listen on `127.0.0.1` or `0.0.0.0`; if they listen only on another interface, sibling containers in the pod may not be able to reach them.
- When the upstream service supports configuring the listen address via environment variables or equivalent runtime settings, preserve or generate the necessary configuration instead of assuming the default bind address is correct.
- When `Pod=` is set, never generate `AddHost=` entries whose purpose is sibling-container discovery inside that pod. Intra-pod communication should use `127.0.0.1` / `localhost` instead.
- `AddHost=` is a host-to-IP override, not an intra-pod service-discovery mechanism. Do not describe `Pod=` as a blanket prohibition on `AddHost=` unless the upstream reference explicitly requires that for the case at hand.
- Containers in different pods must not be treated as reachable via `127.0.0.1` / `localhost`.
- When splitting services across multiple pods or preserving a shared bridge network, use container names, pod names, or explicit `NetworkAlias=` values on the shared network, or publish ports to the host boundary when that is the intended access pattern.
- Do not add `ServiceName=` or `PodName=` by default.
- `ServiceName=` controls the generated systemd unit name only and must not be used as an application-facing network address.
- `PodName=` controls the Podman pod name only; it can participate in the chosen addressing strategy, but it does not determine the systemd service name.

### `environment`, `env_file`, and `.env` interpolation

- Use `references/env-strategy.md` for detailed env handling, interpolation, sensitivity defaults, completeness checks, and missing-variable reporting.

### `profiles`

- Decide first which profiles are actually part of the desired deployment.
- Do not try to preserve Compose profiles as a direct Quadlet concept.
- Treat profiles as source selection inputs that decide which services become units.

### `depends_on`

- Translate to `Requires=` and `After=` when that reflects intent.
- State clearly that this controls startup ordering, not application readiness.

### `healthcheck`

- Prefer dedicated Quadlet health fields such as `HealthCmd=`, `HealthInterval=`, `HealthTimeout=`, `HealthRetries=` when representable.
- If the Compose healthcheck is only partially representable, preserve the command intent and call out missing knobs.

### `command` and `entrypoint`

- `entrypoint` typically maps to `Entrypoint=`.
- `command` typically maps to `Exec=`.
- If an entrypoint or helper script is repo-local, treat it as a support file that must be copied or preserved in the generated layout.

### `user`

- Map `User=` and `Group=` only when the source explicitly requires a container runtime user mapping or when the user is addressing permission or ownership behavior.
- Do not use systemd `User=` to try to make a rootless Quadlet run as another login user.
- When the image declares a fixed non-zero runtime user, or a rootless bind mount hits a UID/GID mismatch, stop and follow `references/runtime-identity.md` for the diagnosis path and `UserNS=keep-id:uid=<container_uid>,gid=<container_gid>` semantics before writing any identity directives.

## Topology Guidance

Choose the simplest topology that preserves the source deployment intent.

- Prefer a single `.pod` for multi-container applications when practical.
- If one logical service contains multiple containers, default to putting them in the same `.pod` so they share networking and lifecycle.
- If the project is a simple single-container deployment with no real need for pod semantics, a standalone `.container` is the preferred result.
- If one pod is not practical because of port conflicts or clearly incompatible groupings, split the result into a small number of pods rather than forcing an awkward topology.
- Avoid preserving bridge networks by default when pod grouping already expresses the intended communication pattern well.
- For large application stacks with optional services, ask the user to choose the desired service set before generating a minimized result.

## Risky Or Lossy Areas

Handle these conservatively and usually as migration notes:

- `deploy`
- `extends`
- advanced Compose merge behavior
- readiness semantics hidden behind `depends_on`
- any mapping that changes the source network or storage behavior in a way that matters

## Minimal Examples

### Single service to standalone container

Source intent:

```yaml
services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
```

Reasonable result shape:

```ini
[Container]
Image=docker.io/library/nginx:latest
PublishPort=8080:80
```

### Small multi-service app to one pod

Source intent:

```yaml
services:
  api:
    image: ghcr.io/example/api:1.0
    depends_on:
      - db
  db:
    image: postgres:16
```

Reasonable result shape:

- one `.pod` for the application boundary
- one container unit for `api`
- one container unit for `db`
- `api` may reach `db` over `127.0.0.1` / `localhost` because both containers share the pod network namespace
- ordering hints for startup, while explicitly noting that `depends_on` does not guarantee readiness
