# Quadlet Creator

[English](./README.md) | [简体中文](./README.zh-CN.md)

Quadlet Creator is a skill for converting Docker-based deployment input into Podman Quadlet output.

## What It Does

- converts `docker run` commands into Quadlet units
- converts Docker Compose setups into Quadlet deployments
- analyzes self-hosting deployment files in GitHub repositories
- keeps env files, mounted config, initialization assets, and helper scripts when they are part of the deployment
- turns large env templates into a short list of deployment decisions
- provides deployment, validation, and troubleshooting guidance

## Installation

```bash
npx skills add https://git.nite07.com/nite/skills.git -g -s quadlet-creator
```

## When To Use It

Use this skill when you want to:

- move a service from Docker to Podman Quadlet
- convert a Compose stack into a Quadlet layout
- review a repository's self-hosting deployment files
- generate files for review before installation
- validate or troubleshoot generated Quadlet files

## How To Use It

1. Give it an input:
   - a `docker run` command
   - a Compose file or Compose project
   - a GitHub repository URL
   - existing Quadlet files that need review or cleanup
2. Say what you want:
   - mapping advice
   - a deployment design
   - reviewable runnable output
3. Confirm deployment-specific values such as domains, host paths, credentials, storage choices, or optional services.
4. Review the generated output before applying it.

## Example Requests

```text
Convert this docker run command into Quadlet and explain the mapping.

Review this compose.yaml and propose a Podman Quadlet layout.

Generate reviewable Quadlet files from this repository's self-hosting deployment.

Help me migrate this stack to rootless Podman and keep the env-file workflow.
```

## Typical Output

- Quadlet unit files
- env files or env deltas
- helper scripts for install, reload, start, stop, restart, and uninstall
- deployment notes and validation guidance

## Notes

- Review generated output before installation.
- Confirm deployment-specific values instead of guessing them.
- Call out behavior changes when Docker Compose and Quadlet do not map cleanly.

## License

MIT
