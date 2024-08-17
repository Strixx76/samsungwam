#!/usr/bin/env python3
"""Helper script for version handling and checks."""
# ruff: noqa: T201

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from homeassistant import const
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import Version

ROOT_PATH = Path(__file__).resolve().parents[1]
INTEGRATION_PATH = (
    ROOT_PATH / "custom_components" / os.getenv("INTEGRATION_PATH", "default")
)
WARNINGS_FILE = ROOT_PATH / "WARNINGS"
# Integration versions
MANIFEST_FILE = INTEGRATION_PATH / "manifest.json"
CHANGELOG_FILE = ROOT_PATH / "CHANGELOG.md"
# Home Assistant versions
HACS_FILE = ROOT_PATH / "hacs.json"
REQUIREMENTS_FILE = ROOT_PATH / "requirements.txt"
REQUIREMENTS_DEV_FILE = ROOT_PATH / "requirements_dev.txt"


class VersionMismatchError(Exception):
    """Exception for when versions does not match."""


class HomeAssistantVersions:
    """All versions of HomeAssistant."""

    installed_version: Version = Version("0.0.0")
    hacs_json_version: Version = Version("0.0.0")
    requirements_version: Version = Version("0.0.0")
    stubs_version: Version = Version("0.0.0")

    def compare_versions(self) -> None:
        """Compare versions of Home Assistant.

        Raises:
            VersionMismatchError: When Home Assistant versions does not
            match.
        """
        if self.installed_version != self.hacs_json_version:
            raise VersionMismatchError(
                f"Installed version ({self.installed_version}) does not match "
                f"hacs.json version ({self.hacs_json_version})"
            )
        if self.installed_version != self.requirements_version:
            raise VersionMismatchError(
                f"Installed version ({self.installed_version}) does not match "
                f"requirements version ({self.requirements_version})"
            )
        if self.installed_version != self.stubs_version:
            raise VersionMismatchError(
                f"Installed version ({self.installed_version}) does not match "
                f"stubs version ({self.stubs_version})"
            )
        if self.hacs_json_version != self.requirements_version:
            raise VersionMismatchError(
                f"hacs.json version ({self.hacs_json_version}) does not match "
                f"requirements version ({self.requirements_version})"
            )
        if self.hacs_json_version != self.stubs_version:
            raise VersionMismatchError(
                f"hacs.json version ({self.hacs_json_version}) does not match "
                f"stubs version ({self.stubs_version})"
            )
        if self.requirements_version != self.stubs_version:
            raise VersionMismatchError(
                f"requirements version ({self.requirements_version}) does not match "
                f"stubs version ({self.stubs_version})"
            )


class IntegrationVersions:
    """All versions of the integration."""

    manifest_version: Version = Version("0.0.0")
    changelog_version: Version = Version("0.0.0")

    def compare_versions(self) -> None:
        """Compare versions of the integration.

        Raises:
            VersionMismatchError: When integration versions does not
            match.
        """
        if self.manifest_version != self.changelog_version:
            raise VersionMismatchError(
                f"Manifest version ({self.manifest_version}) does not match "
                f"changelog version ({self.changelog_version})"
            )


class DependencyRequirements:
    """All dependency packages."""

    manifest_versions: list[Requirement] = []
    requirements_versions: list[Requirement] = []

    def compare_versions(self) -> None:
        """Compare dependency packages.

        Raises:
            VersionMismatchError: When dependency versions does not
            match.
        """
        if self.manifest_versions != self.requirements_versions:
            raise VersionMismatchError(
                f"Manifest requirements ({self.manifest_versions}) does not match "
                f"requirements in requirements.txt ({self.requirements_versions})\n"
                f"Or perhaps they are not in the same order."
            )


def get_ha_versions() -> HomeAssistantVersions:
    """Get Home Assistant versions.

    Returns:
        Current versions of Home Assistant.
    """
    home_assistant_versions = HomeAssistantVersions()

    home_assistant_versions.installed_version = Version(const.__version__)

    with open(HACS_FILE) as json_file:
        data = json.load(json_file)
        home_assistant_versions.hacs_json_version = Version(data["homeassistant"])

    with open(REQUIREMENTS_FILE) as txt_file:
        for line in txt_file:
            if line.startswith("homeassistant=="):
                home_assistant_versions.requirements_version = Version(
                    line.split("==")[1]
                )
                break

    with open(REQUIREMENTS_DEV_FILE) as txt_file:
        for line in txt_file:
            if line.startswith("homeassistant-stubs=="):
                home_assistant_versions.stubs_version = Version(line.split("==")[1])
                break

    return home_assistant_versions


def get_integration_versions() -> IntegrationVersions:
    """Get integration versions.

    Returns:
        Current versions of the integration.
    """
    integration_versions = IntegrationVersions()

    with open(MANIFEST_FILE) as json_file:
        data = json.load(json_file)
        integration_versions.manifest_version = Version(data["version"])

    with open(CHANGELOG_FILE) as txt_file:
        for line in txt_file:
            if line.startswith("## "):
                ver = line.split()[1].replace("[", "").replace("]", "")
                if ver == "unreleased":
                    continue
                integration_versions.changelog_version = Version(ver)
                break

    return integration_versions


def get_dependency_versions() -> DependencyRequirements:
    """Get dependency package versions.

    Returns:
        Current dependencies in the project.
    """
    dependency_versions = DependencyRequirements()

    with open(MANIFEST_FILE) as json_file:
        data = json.load(json_file)
        for item in data["requirements"]:
            dependency_versions.manifest_versions.append(Requirement(item))

    with open(REQUIREMENTS_FILE) as txt_file:
        for line in txt_file:
            if not line.startswith("homeassistant=="):
                dependency_versions.requirements_versions.append(Requirement(line))

    return dependency_versions


def print_versions(
    home_assistant_versions: HomeAssistantVersions,
    integration_versions: IntegrationVersions,
    dependency_versions: DependencyRequirements,
    to_file: bool = False,
):
    """Print versions.

    Arguments:
        home_assistant_versions:
            Current Home Assistant versions.
        integration_versions:
            Current integration versions.
        dependency_versions:
            Current dependencies.
        to_file:
            `True` to print to file.
    """
    if to_file:
        out_put = open(WARNINGS_FILE, "w")
    else:
        out_put = None

    print("\n\n", file=out_put)
    print("Home Assistant versions in the project", file=out_put)
    print("--------------------------------------", file=out_put)
    print(
        f"Installed in container:       {home_assistant_versions.installed_version}",
        file=out_put,
    )
    print(
        f"Min version in hacs.json:     {home_assistant_versions.hacs_json_version}",
        file=out_put,
    )
    print(
        f"Version in requirements.txt:  {home_assistant_versions.requirements_version}",
        file=out_put,
    )
    print(
        f"homeassistant-stubs version:  {home_assistant_versions.stubs_version}",
        file=out_put,
    )
    print("", file=out_put)
    print("Integration versions in the project", file=out_put)
    print("-----------------------------------", file=out_put)
    print(
        f"Manifest version:      {integration_versions.manifest_version}", file=out_put
    )
    print(
        f"Changelog version:     {integration_versions.changelog_version}", file=out_put
    )
    print("", file=out_put)
    print("Dependency versions in the project", file=out_put)
    print("----------------------------------", file=out_put)
    print(
        f"Manifest version:             {[str(dep) for dep in dependency_versions.manifest_versions]}",
        file=out_put,
    )
    print(
        f"Version in requirements.txt:  {[str(dep) for dep in dependency_versions.requirements_versions]}",
        file=out_put,
    )


def compare_versions(
    home_assistant_versions: HomeAssistantVersions,
    integration_versions: IntegrationVersions,
    dependency_versions: DependencyRequirements,
):
    """Compare versions.

    If version does not match, print versions to file and screen.

    Arguments:
        home_assistant_versions:
            Current Home Assistant versions.
        integration_versions:
            Current integration versions.
        dependency_versions:
            Current dependencies.
    """
    try:
        home_assistant_versions.compare_versions()
        integration_versions.compare_versions()
        dependency_versions.compare_versions()
    except VersionMismatchError as err:
        print_versions(
            home_assistant_versions, integration_versions, dependency_versions
        )
        print_versions(
            home_assistant_versions, integration_versions, dependency_versions, True
        )
        print(err)

        return

    WARNINGS_FILE.unlink(missing_ok=True)


def validate_home_assistant_version(input_version: str) -> str:
    """Validate Home Assistant version.

    Arguments:
        input_version:
            Version to validate.

    Returns:
        Validated Home Assistant version.

    Raises:
        argparse.ArgumentTypeError:
            If input_version is not a correct version.
    """
    if not re.fullmatch(r"^\d{4}\.\d{1,2}\.\d{1}", input_version):
        raise argparse.ArgumentTypeError("Invalid Home Assistant version")

    return input_version


def validate_dependency_requirement(input_requirement: str) -> str:
    """Validate dependency requirement.

    Arguments:
        input_requirement:
            Requirement to validate.

    Returns:
        Validated requirement.

    Raises:
        argparse.ArgumentTypeError:
            If requirement doesn't follow PEP 508.
    """
    try:
        Requirement(input_requirement)
    except InvalidRequirement as err:
        raise argparse.ArgumentTypeError from err

    return input_requirement


def new_home_assistant_version(new_version: Version):
    """Change version of Home Assistant.

    Arguments:
        new_version:
            New version of Home Assistant.
    """
    with open(HACS_FILE) as json_file:
        data = json.load(json_file)
    data["homeassistant"] = str(new_version)
    with open(HACS_FILE, "w") as json_file:
        json.dump(data, json_file, indent=2)

    with open(REQUIREMENTS_FILE) as txt_file:
        requirements: list[str] = []
        for line in txt_file:
            if line.startswith("homeassistant=="):
                requirements.append(f"homeassistant=={str(new_version)}\n")
            else:
                requirements.append(line)
    with open(REQUIREMENTS_FILE, "w") as txt_file:
        txt_file.writelines(requirements)

    with open(REQUIREMENTS_DEV_FILE) as txt_file:
        requirements_dev: list[str] = []
        for line in txt_file:
            if line.startswith("homeassistant-stubs=="):
                requirements_dev.append(f"homeassistant-stubs=={str(new_version)}\n")
            else:
                requirements_dev.append(line)
    with open(REQUIREMENTS_DEV_FILE, "w") as txt_file:
        txt_file.writelines(requirements_dev)


def new_dependency_requirements(
    new_dep_version: Requirement, dependency_requirements: DependencyRequirements
):
    """Change version or add new dependencies.

    Arguments:
        new_dep_version:
            New or updated requirement.
        dependency_requirements:
            Current dependencies.
    """
    # Update or add new dependency.
    if new_dep_version.name not in [
        dep.name for dep in dependency_requirements.manifest_versions
    ]:
        dependency_requirements.manifest_versions.append(new_dep_version)
    else:
        idx = [
            dependency_requirements.manifest_versions.index(dep)
            for dep in dependency_requirements.manifest_versions
            if dep.name == new_dep_version.name
        ][0]
        dependency_requirements.manifest_versions[idx] = new_dep_version

    # Update manifest file.
    with open(MANIFEST_FILE) as json_file:
        data = json.load(json_file)
    data["requirements"] = sorted(
        [str(dep) for dep in dependency_requirements.manifest_versions]
    )
    with open(MANIFEST_FILE, "w") as json_file:
        json.dump(data, json_file, indent=2)

    # Update requirement file.
    with open(REQUIREMENTS_FILE) as txt_file:
        for line in txt_file:
            if line.startswith("homeassistant=="):
                new_requirements = [line]
                break

    new_requirements.extend(
        [f"{str(dep)}\n" for dep in dependency_requirements.manifest_versions]
    )
    with open(REQUIREMENTS_FILE, "w") as txt_file:
        txt_file.writelines(sorted(new_requirements))


def bump_integration_version(integration_versions: IntegrationVersions, bump_type: str):
    """Bump version of integration.

    Arguments:
        integration_versions:
            Current integration versions.
        bump_type:
            `patch`, `minor` or `major` bump of version.
    """
    major, minor, patch = integration_versions.manifest_version.release

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0

    new_version = f"{major}.{minor}.{patch}"

    with open(MANIFEST_FILE) as json_file:
        data = json.load(json_file)
    data["version"] = new_version
    with open(MANIFEST_FILE, "w") as json_file:
        json.dump(data, json_file, indent=2)

    with open(CHANGELOG_FILE) as txt_file:
        change_log = txt_file.readlines()
    change_log.insert(0, f"# {new_version} ({datetime.today().strftime('%Y-%m-%d')})\n")
    with open(CHANGELOG_FILE, "w") as txt_file:
        txt_file.writelines(change_log)

    print("Bumped integration version to ", new_version)
    print("Please add changes to the CHANGELOG.md file")


def main():
    """Execute script."""
    home_assistant_versions = get_ha_versions()
    integration_versions = get_integration_versions()
    dependency_requirements = get_dependency_versions()

    parser = argparse.ArgumentParser(description="check and bump versions.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compare", help="compare versions", action="store_true")
    group.add_argument("-p", "--print", help="print versions", action="store_true")
    group.add_argument(
        "-n",
        "--new_ha_ver",
        help="new Home Assistant version",
        type=validate_home_assistant_version,
    )
    group.add_argument(
        "-d",
        "--new_dep_ver",
        help="new package dependency version",
        type=validate_dependency_requirement,
    )
    group.add_argument(
        "-b",
        "--bump",
        choices=["patch", "minor", "major"],
        help="Bump integration version",
    )
    args = parser.parse_args()

    if args.compare:
        compare_versions(
            home_assistant_versions, integration_versions, dependency_requirements
        )

    if args.print:
        print_versions(
            home_assistant_versions, integration_versions, dependency_requirements
        )

    if args.new_ha_ver:
        try:
            home_assistant_versions.compare_versions()
        except VersionMismatchError:
            print_versions(
                home_assistant_versions, integration_versions, dependency_requirements
            )
            print("ERROR: Version mismatch")
            print("Can't change Home Assistant version.")
            return
        new_home_assistant_version(Version(args.new_ha_ver))

    if args.new_dep_ver:
        try:
            dependency_requirements.compare_versions()
        except VersionMismatchError:
            print_versions(
                home_assistant_versions, integration_versions, dependency_requirements
            )
            print("ERROR: Version mismatch")
            print("Can't change dependency versions.")
            return
        new_dependency_requirements(
            Requirement(args.new_dep_ver), dependency_requirements
        )

    if args.bump:
        try:
            integration_versions.compare_versions()
        except VersionMismatchError:
            print_versions(
                home_assistant_versions, integration_versions, dependency_requirements
            )
            print("ERROR: Version mismatch")
            print("Can't bump integration version.")
            return
        bump_integration_version(integration_versions, args.bump)


if __name__ == "__main__":
    main()
