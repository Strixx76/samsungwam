#!/bin/bash

set -euo pipefail

# Change to project root
cd "$(dirname "$0")/.."

# Store config directory
readonly config_dir="${PWD}/.devcontainer/preconfig"


# Check if preconf is set up
if [[ ! -d "${config_dir}" ]]; then
    echo "Preconfiguration not yet done!" >&2
    echo "Please run task 'Configure Home Assistant' first." >&2
    exit 1
fi


# Create custom_components directory if not existing
if ! [[ -d "${config_dir}/custom_components" ]]; then
    mkdir -p "${config_dir}/custom_components"
fi
# Create symlink to project custom component directory
if ! [[ -d "${config_dir}/custom_components/${INTEGRATION_PATH}" ]]; then
    ln -s "${PWD}/custom_components/${INTEGRATION_PATH}" "${config_dir}/custom_components/${INTEGRATION_PATH}"
fi


# Start Home Assistant
hass --c "${config_dir}" --debug