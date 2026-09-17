#!/bin/sh
set -eu

# Start the reviewed lifecycle unit(s).
# Update the variables and systemctl_cmd() function below before using this template.

LIFECYCLE_UNITS='app-pod.service'

systemctl_cmd() {
	systemctl --user "$@"
}

for unit in $LIFECYCLE_UNITS; do
	systemctl_cmd start "$unit"
done
