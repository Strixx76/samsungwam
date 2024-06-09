#!/bin/bash

set -euo pipefail

# Change to project root
cd "$(dirname "$0")/.."

# Store config directory
readonly source_dir="${PWD}/.devcontainer/.stored_config"
readonly target_dir="${PWD}/.devcontainer/preconfig"

# Delete present configs
echo "Removing old configurations..." >&2
rm -rfv "${target_dir}"
mkdir -pv "${target_dir}"

# Copy files
echo "Setting up preconfig..." >&2
cp -av "${source_dir}/." "${target_dir}/"

# Set up user admin with password admin
echo "Setting user and password..." >&2
readonly password_file="${target_dir}/.storage/auth_provider.homeassistant"
if [[ -f "${password_file}" ]]; then
    readarray -t users < <(jq --raw-output --compact-output '.data.users[].username' "${password_file}")
    for user in "${users[@]}"; do
        echo "Setting password for user '${user}' to 'admin'" >&2
        password=$(jq --exit-status --raw-output --arg u "${user}" '.data.users[] | select(.username==$u) | .password' "${password_file}")
        hass --script auth --c "${target_dir}" change_password "${user}" "${password}"
    done
fi

echo "Preconfigured successfully" >&2