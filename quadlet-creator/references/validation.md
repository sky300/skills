# Validation

Use this file when the user asks how to verify or troubleshoot generated Quadlet units.

## Contents

- Validation flow
- Verification commands
- Runnable-output checks
- Common failure causes
- Troubleshooting posture

## Validation Flow

Validation belongs after execution, after the reviewed Quadlet files have been applied to a valid Quadlet directory, and while the referenced support files still exist at the host paths used by the generated units.

Recommended validation flow:

1. Confirm the user already reviewed the finalize snapshot and approved execution.
2. Confirm the generated deliverable set contains the expected Quadlet units, env files, helper scripts, and required support files.
3. Run `install.sh` to copy only the reviewed Quadlet unit files into the target Quadlet directory.
4. Run the appropriate reload command.
5. Start the relevant units and inspect their status.
6. If needed, run `uninstall.sh` to remove the installed reviewed artifact set before regenerating or abandoning the deployment.

If the user requested an alternate apply script name explicitly, substitute that name where needed, but treat `install.sh` as the default documentation path.

## Verification Commands

### Rootless

```bash
systemctl --user daemon-reload
systemctl --user start <unit>
systemctl --user status <unit>
```

### Rootful

```bash
systemctl daemon-reload
systemctl start <unit>
systemctl status <unit>
```

### Generator debugging

Use the Podman systemd generator dry run when units fail to appear or options look unsupported.

The generator is installed by your Podman package, so its path depends on that package and on the distribution: resolve it before running instead of assuming one. `<generator path>` below stands for that resolved path and is the user's environment's decision, not this skill's. The common location is `/usr/lib/systemd/system-generators/podman-system-generator` (the bare name is normally not on `PATH`); some installations place it under `/usr/local/lib/systemd/system-generators/`.

```bash
<generator path> --dryrun
```

For rootless debugging:

```bash
<generator path> --user --dryrun
```

### Systemd verification

```bash
systemd-analyze verify <unit>.service
```

For user units:

```bash
systemd-analyze --user verify <unit>.service
```

## Runnable-Output Checks

Before calling the result runnable, verify that:

- every referenced `EnvironmentFile=` exists at the path referenced by the installed unit
- required env keys are present in the final env sources, or are explicitly surfaced as unresolved placeholders
- bind-mounted files and directories exist at the absolute paths referenced by the generated Quadlet files
- bind-mounted file-versus-directory shape still matches the source input
- if `AutoUpdate=registry` is enabled, the generated unit uses a fully qualified image reference
- when sibling containers in the same pod must connect to a service, its effective listen address is reachable within the pod namespace (`127.0.0.1` or `0.0.0.0`, unless upstream docs require another reviewed bind address)
- repo-local entrypoint or helper scripts referenced by the container exist and are executable when needed
- initialization assets such as `init.sql`, seeds, bootstrap files, or config templates are present where the deployment expects them
- service-management scripts operate on the same reviewed artifact set that finalize approved
- helper shell scripts match reviewed Quadlet files by their shared generated prefix with globbing such as `<prefix>*`, not hardcoded filenames or assumed file counts

Runnable-output gate checklist template:

- [ ] the support-file set is complete
- [ ] every `EnvironmentFile=` path resolves to an actual reviewed file
- [ ] env completeness check passed against the actual final env sources
- [ ] startup-critical env keys are present, or explicitly marked as unresolved placeholders
- [ ] unit files are installed in the intended Quadlet directory
- [ ] support files remain available at the absolute paths expected by mounts and scripts
- [ ] bind-mounted file-versus-directory shape still matches the source input
- [ ] if `AutoUpdate=registry` is enabled, the generated unit uses a fully qualified image reference
- [ ] intra-pod service listeners that must accept sibling-container traffic are reachable on `127.0.0.1` or `0.0.0.0`, unless upstream docs require another reviewed bind address
- [ ] service-management scripts operate on the same artifact set that was reviewed
- [ ] no required support file, env key, or typo-suspect mismatch remains unresolved
- [ ] host-side `PublishPort=` ports are free on the target host

Do not call the result runnable until every item above is checked.

## Common Failure Causes

- unsupported Quadlet option for the installed Podman version
- `AutoUpdate=registry` was enabled but the image reference is not fully qualified
- bind-mount source directory missing
- rootless bind-mount UID/GID mismatch between the image's runtime user and the host path owner — diagnose with `references/runtime-identity.md` instead of trying mount flags
- files were generated but `install.sh` has not yet copied the unit files into the target rootless or rootful unit directory
- wrong rootless or rootful apply target directory
- unresolved env file path
- required env key missing from the final env file
- likely env-key typo or mismatch between source docs and final env output
- required repo-local config, init assets, or helper scripts missing from the installed artifact set
- permissions on rootless bind mounts
- readiness assumptions hidden behind `depends_on`
- host port already in use by another service or process, causing `PublishPort=` binding to fail at start

## Troubleshooting Posture

When validation fails, report:

- what generated successfully
- what was applied successfully
- what failed to generate, apply, or start
- whether the issue is syntax, unsupported feature, path resolution, installation path, missing support files, missing env keys, or permissions
