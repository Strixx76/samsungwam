#!/bin/bash

set -euo pipefail

# Change to project root
cd "$(dirname "$0")/.."

# Store config directory
readonly config_dir="${PWD}/.devcontainer/config"


# Create configs if not existing
if [[ ! -d "${config_dir}" ]]; then
    mkdir -p "${config_dir}"
    hass --config "${config_dir}" --script ensure_config
fi


# Create custom_components directory if not existing
if ! [[ -d "${config_dir}/custom_components" ]]; then
    mkdir -p "${config_dir}/custom_components"
fi
# Create symlink to project custom component directory
if ! [[ -d "${config_dir}/custom_components/${INTEGRATION_PATH}" ]]; then
    ln -s "${PWD}/custom_components/${INTEGRATION_PATH}" "${config_dir}/custom_components/${INTEGRATION_PATH}"
fi


# Install local pip packages
pip install -e /home/vscode/package --config-settings editable_mode=strict

# Start Home Assistant
hass --c "${config_dir}" --debug --skip-pip-packages "${PIP_PACKAGE}"