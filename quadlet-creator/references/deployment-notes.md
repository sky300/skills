# Deployment Notes

Use this file when the user wants deployment-ready instructions alongside generated Quadlet units.

## Contents

- Delivery flow
- Apply target directories
- Helper-script expectations
- Operational notes
- Optional enhancements

## Delivery Flow

For `design` mode, stop after the user reviews the finalize snapshot in conversation.
For `generate` mode, continue only after the user has reviewed and confirmed the finalize snapshot or requested edits.

Recommended apply flow:

1. Generate the reviewable artifacts in the current working directory by default, or in another user-requested output directory.
2. Review the finalized design together with the generated Quadlet files, env files, helper scripts, and required repo-local support files.
3. Use `install.sh` to copy only the reviewed Quadlet unit files into the chosen Quadlet directory.
4. Run the appropriate `daemon-reload` command.
5. Use `start.sh`, `stop.sh`, and `restart.sh` to manage services.
6. Use `uninstall.sh` only when the user wants to remove the installed reviewed Quadlet unit files without broad Podman cleanup.

Keep installation separate from service-management scripts so the user can review generated files before applying them.

## Apply Target Directories

These are Quadlet's documented default search paths, not a location this skill assumes: the deployment mode decides which one applies, and the user's environment can move the rootless path (it follows `$XDG_CONFIG_HOME`, falling back to the `~/.config` form below). Confirm the actual target directory with the user before installing.

### Rootless

- default apply target: `~/.config/containers/systemd/`
- user-scoped management commands use `systemctl --user`

### Rootful

- default apply target: `/etc/containers/systemd/`
- system-scoped management commands use `systemctl`

See `podman-systemd.unit.5.md` for the full search-path matrix.

## Helper-Script Expectations

- `install.sh` is the canonical apply script. It copies only reviewed Quadlet unit files into the selected Quadlet target directory. Start from `templates/install_template.sh`, which carries the prefix-glob copy logic and the variables to set.
- Do not generate a separate `apply.sh` by default. Use that alternate name only when the user explicitly asks for it.
- Helper shell scripts must discover the reviewed Quadlet files through their shared generated prefix, using shared-prefix glob matching such as `<prefix>*` instead of hardcoding exact filenames or assuming a fixed file count.
- `install.sh` must not start, stop, restart, or reload services as a side effect.
- `uninstall.sh` removes only the installed reviewed Quadlet unit files from the selected Quadlet target directory.
- `uninstall.sh` should stop affected services before removing their installed unit files, and should not delete support files, unrelated files, shared directories, named volumes, images, or Podman objects unless the user explicitly asks for broader cleanup.
- `reload.sh` runs only the appropriate `daemon-reload` command after installation changes.
- `start.sh`, `stop.sh`, and `restart.sh` manage services only and must not silently install or overwrite reviewed files.
- When a generated topology includes `<name>.pod` plus child containers linked with `Pod=<name>.pod`, helper scripts should use the pod service as the lifecycle entrypoint. Derive that service name from `ServiceName=` when present on the `.pod`, otherwise use Quadlet's default generated pod service name. Do not add `ServiceName=` merely to simplify helper scripts.

## Operational Notes

- Review not only Quadlet unit files but also env files, mounted config, initialization assets, entrypoint scripts, and other support files required at runtime.
- Do not add explicit runtime naming directives such as `PodName=`, `ServiceName=`, `ContainerName=`, or `NetworkName=` by default. Use Quadlet's derived names unless the user explicitly asks for custom naming or a reviewed requirement depends on it.
- Do not use `ServiceName=` as an application connection target. It controls the generated systemd unit name only.
- Within a single pod, use `127.0.0.1` / `localhost` for container-to-container communication instead of generating `AddHost=` entries for sibling-container discovery.
- If a service inside the pod must accept connections from sibling containers, ensure its effective listen address is reachable within the shared pod namespace, typically `127.0.0.1` or `0.0.0.0`.
- Bind mounts may hit UID/GID mismatches, especially in rootless deployments. Diagnose and resolve these with `references/runtime-identity.md` rather than patching mount flags.
- Do not add `User=`, `Group=`, or `UserNS=` speculatively. Add them only after the diagnosis path in `references/runtime-identity.md` confirms an identity mismatch, or when the source explicitly requires that runtime identity mapping.
- For rootless long-running services that should survive logout, mention lingering:

```bash
sudo loginctl enable-linger <username>
```

- Ensure bind-mount source directories exist before first start.
- Normalize relative source paths against the source Compose file directory or the directory the user specifies.
- Emit absolute host paths in generated Quadlet files when using bind mounts.

## Optional Enhancements

- `AutoUpdate=registry` for opt-in automatic image refresh workflows when the approved image strategy uses fully qualified registry images
- explicit `.volume` or `.network` units when the user wants declarative infrastructure instead of implicit Podman objects
- service defaults such as:

```ini
[Service]
Restart=always
TimeoutStartSec=900
```

Use the timeout especially when first start may need to pull large images or build locally.

## Output Language

If you generate a README, deployment note, or operator-facing document as part of the migration, write it in the user's language unless the user explicitly asks for another language.
