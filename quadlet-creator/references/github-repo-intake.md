# GitHub Repository Intake

Use this file when the user provides a GitHub repository URL and expects you to find the deployment inputs yourself.

## Contents

- Goal
- Discovery order
- What to extract
- Heuristics
- Support-file checklist
- Reporting expectations

## Goal

Discover the canonical self-hosting assets before attempting any Quadlet conversion.

## Discovery order

1. Read the repository `README.md`.
2. Look for self-hosting instructions and explicit references to Compose files.
3. If documentation names a path, follow that path first.
4. Search the repository tree for likely deployment files:
   - `docker-compose.yaml`
   - `docker-compose.yml`
   - `compose.yaml`
   - `compose.yml`
   - `.env.example`
   - `.env.sample`
   - `env.example`
   - `middleware.env.example`
5. Inspect likely deployment directories when needed:
   - `docker/`
   - `deploy/`
   - `ops/`
   - `infra/`
   - `examples/`
   - `.devcontainer/`
6. Read deployment-specific README files in those directories.
7. Identify helper scripts that generate or sync compose files.
8. Identify repo-local companion files required at runtime, such as mounted config, templates, initialization files, seed data, bootstrap assets, entrypoint scripts, and bind-mounted directory trees.

## What to extract

- canonical compose file path
- companion env template path
- additional compose files used for middleware or optional services
- repo-local companion files required for runtime, such as config, templates, initialization files, bootstrap assets, entrypoint scripts, or mounted directories
- whether the compose file is generated
- whether the source relies on profiles
- whether startup requires preparatory steps such as copying `.env.example` to `.env`
- whether those companion files must be copied, rendered, or kept in a specific relative layout for the deployment to work

## Heuristics

- Prefer the path explicitly linked from the main README over a randomly discovered file.
- Do not hardcode assumptions like "the deployment entry point is always under `docker/`".
- If the repo has both a template and a generated compose file, treat the generated file as the runnable source and the template as explanatory context.
- If profiles control optional databases or vector stores, decide which profile set the user actually wants before generating Quadlet.
- If env management is mandatory, preserve that pattern rather than flattening hundreds of variables into inline `Environment=` values.
- If the source mounts or references repo-local config, templates, initialization assets, entrypoint scripts, or directory trees, treat them as first-class deployment inputs rather than incidental files.
- If a Compose bind mount points to a repo-relative file or directory, treat that path as a candidate support-file source rather than only recording the mount string.
- If docs or startup scripts say to copy, edit, mount, or render a repo-local file before startup, include that asset in the deliverable review set.
- If a whole directory is mounted, inspect the directory contents and preserve the required files instead of only naming the directory root.
- Do not reduce runnable output to only Quadlet plus env when the source project depends on additional repo-local assets.
- If several candidate compose files exist, explain which one you selected and why.

## Support-file checklist

Before choosing the final source of truth, confirm:

- which repo-local files are mounted directly
- which repo-local directories are mounted as whole trees
- which startup docs require copying, editing, or rendering companion files
- which entrypoint or helper scripts refer to additional local assets
- which companion files are mandatory for minimal startup versus optional extras

Use this checklist to prevent reducing the deliverable to Quadlet plus env when the source project depends on more than that.

## Reporting expectations

When converting a GitHub-hosted project, report:

- which files you chose as source of truth
- which required repo-local companion files must ship with the result
- which optional files or profiles you ignored
- which variables still require user decisions
