# Environment Strategy

Use this file whenever the migration includes `.env`, `env_file`, Compose interpolation, or inline `-e` flags.

## Contents

- Goals
- Default rules
- Sensitive values
- Interpolation
- Completeness validation
- Examples and checklists

## Goals

- preserve source-of-truth for variables
- avoid leaking secrets into generated Quadlet files by default
- keep resulting units readable
- report missing variables explicitly
- reduce large upstream env templates into a small set of user decisions
- validate env completeness before claiming runnable output

## Default rules

The agent should actively interpret the env template and its comments. Do not offload the entire env review back to the user.

Runnable output requires an env completeness check, not just env summarization.
A variable is not considered satisfied unless it is present in one of the actual final output sources:

- `Environment=` in generated Quadlet
- the final `EnvironmentFile=` contents
- a documented default that is intentionally preserved in the runnable result
- an explicit placeholder, but only when the result is intentionally not yet runnable

If a variable is still absent from the actual output sources, keep it unresolved.
Do not silently downgrade a startup-critical variable into an informational note.

### Prefer `Environment=` when

- there are only a few variables
- values are stable and not sensitive
- keeping everything in one file materially improves readability

### Prefer `EnvironmentFile=` when

- the source already uses `.env` or `env_file`
- variables are numerous
- variables contain secrets or deployment-specific values
- the same env file is shared by multiple services

## Sensitive-value heuristic

Treat names containing these substrings as sensitive unless the user tells you otherwise:

- `PASSWORD`
- `TOKEN`
- `SECRET`
- `KEY`
- `PRIVATE`
- `PASS`

Default behavior:

- do not inline them in `Environment=`
- keep them in `EnvironmentFile=` or generate a placeholder sample file instead

## Compose interpolation

Common forms:

- `${VAR}`
- `${VAR:-default}`
- `${VAR-default}`

Strategy:

- if the actual value source is present, resolve it and document where it came from
- if only a default is available, note that the value is default-derived
- if the variable is missing, list it as unresolved

Do not fabricate values.

## Env completeness validation

Before producing runnable artifacts:

- compare variables referenced by Compose, interpolation, docs, startup scripts, and image-specific setup guidance against the variables present in the final output
- verify that every `EnvironmentFile=` referenced in the final result actually contains the required keys the service depends on
- treat missing bootstrap credentials for common stateful services as unresolved required variables, not optional omissions
- if a high-similarity near-match exists, flag it as a likely typo instead of silently accepting it

Examples of suspicious mismatches:

- `POSTGRES_PASSWRD` vs `POSTGRES_PASSWORD`
- singular/plural mismatches such as `ALLOWED_HOST` vs `ALLOWED_HOSTS`
- prefix mismatches where the docs and final env disagree on the canonical key name

If a required key is mentioned in the source docs, image guidance, or startup scripts but is absent from the final output sources, stop before claiming runnable output.

## Agent responsibility

When the source project ships a large `.env.example` or multiple env templates:

- read the comments and deployment docs yourself
- determine which values can safely stay at documented defaults
- determine which values are true deployment decisions and must be confirmed with the user
- prepare a candidate `.env` or env delta instead of asking the user to read the whole template manually
- verify that the final env output still contains the variables needed for minimal startup

The user should only need to answer the small number of high-impact questions that cannot be discovered locally.

## Minimal examples

`<path to the reviewed env file>` in these examples is a deliberate placeholder: the env file's location comes from the deployment the user approved, and this skill never assumes one. Ask for or confirm it instead of reusing an example path.

### Inline stable values

Source intent:

```yaml
environment:
  APP_ENV: production
  APP_PORT: "8080"
```

Reasonable result shape:

```ini
[Container]
Environment=APP_ENV=production
Environment=APP_PORT=8080
```

Use this when there are only a few non-sensitive structural values.

### Preserve env-file workflow

Source intent:

```yaml
env_file:
  - .env
```

Reasonable result shape:

```ini
[Container]
EnvironmentFile=<path to the reviewed env file>
```

Use this when the source already relies on an env file, especially for secrets or many variables.

### Large template reduced to a candidate env

Source intent:

- upstream ships `.env.example`
- only a few values are true deployment decisions

Recommended behavior:

- keep documented defaults that are safe to preserve
- ask the user only for high-impact values such as domain, storage path, or database password
- generate a candidate `.env` or env delta with clear placeholders for the unresolved items

### Required startup variable still missing

Source intent:

```ini
[Container]
EnvironmentFile=<path to the reviewed env file>
Environment=APP_ENV=production
Environment=APP_PORT=8080
```

If the referenced env file does not contain `APP_SECRET`, do not treat this as runnable output.
Report `APP_SECRET` as unresolved and stop before final runnable generation.

## Output patterns

### Small inline set

```ini
[Container]
Environment=APP_ENV=production
Environment=APP_PORT=8080
```

### External env file

```ini
[Container]
EnvironmentFile=<path to the reviewed env file>
```

### Mixed pattern

Use this when a few values are structural and the rest are secret or deployment-specific.

```ini
[Container]
Environment=APP_ENV=production
EnvironmentFile=<path to the reviewed env file>
```

## Finalize checklist template

Before freezing the env plan, confirm:

- which keys are satisfied by `Environment=`
- which keys are satisfied by the final `EnvironmentFile=`
- which keys are preserved via documented defaults
- which keys remain unresolved and therefore block runnable output
- which keys look like typo candidates and need human confirmation

## Execution checklist template

Before writing runnable artifacts, confirm:

- the final env file contains every required startup key
- every `EnvironmentFile=` path in the generated Quadlet matches an actual generated or preserved file
- placeholder values are clearly marked and do not masquerade as confirmed production values
- typo-suspect keys are either corrected or explicitly surfaced in the output

## Missing-variable reporting

When variables cannot be resolved, report them as a concrete checklist.

Example:

- missing `DB_PASSWORD`
- missing `APP_VERSION`
- missing `UPLOAD_LOCATION`
- likely typo: `POSTGRES_PASSWRD` should probably be `POSTGRES_PASSWORD`

If the user asks for scaffolding, generate a sample env file with obvious placeholders.

Even when the user does not explicitly ask for scaffolding, produce a candidate env result when that materially advances the migration.
