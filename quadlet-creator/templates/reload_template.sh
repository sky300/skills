#!/bin/sh
set -eu

# Reload systemd after reviewed Quadlet unit changes.
# Update the systemctl_cmd() function below before using this template.

systemctl_cmd() {
	systemctl --user "$@"
}

systemctl_cmd daemon-reload
