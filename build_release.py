#!/usr/bin/env python3
"""
Build and release script for Intelbras Alarm Home Assistant Integration.

This script:
1. Asks for version or suggests the next version
2. Updates manifest.json with the new version
3. Creates a properly structured zip file for HACS
4. Creates git tag and GitHub release
5. Uploads the zip file to the release
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=True)
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {cmd}")
        print(f"   Error: {e.stderr if e.stderr else e}")
        sys.exit(1)


def get_current_version():
    """Get the current version from manifest.json."""
    manifest_path = Path("custom_components/intelbras_alarm/manifest.json")
    if not manifest_path.exists():
        print("❌ manifest.json not found!")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    return manifest.get("version", "1.0.0")


def suggest_next_version(current_version):
    """Suggest the next version based on current version."""
    try:
        parts = current_version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        suggestions = {
            "1": f"{major}.{minor}.{patch + 1}",  # Patch
            "2": f"{major}.{minor + 1}.0",  # Minor
            "3": f"{major + 1}.0.0",  # Major
        }

        return suggestions
    except (ValueError, IndexError):
        return {"1": "1.0.1", "2": "1.1.0", "3": "2.0.0"}


def update_manifest_version(version):
    """Update the version in manifest.json."""
    manifest_path = Path("custom_components/intelbras_alarm/manifest.json")

    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest["version"] = version

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅ Updated manifest.json to version {version}")


def create_hacs_compatible_zip(version):
    """Create a HACS-compatible zip file with correct structure."""
    zip_filename = "intelbras_alarm.zip"
    source_dir = Path("custom_components/intelbras_alarm")

    # Remove old zip if exists
    if os.path.exists(zip_filename):
        os.remove(zip_filename)

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                # Skip unwanted files
                if any(skip in str(file_path) for skip in ["__pycache__", ".DS_Store", ".pyc"]):
                    continue

                # Add file to zip with relative path (no extra folder level)
                relative_path = file_path.relative_to(source_dir)
                zipf.write(file_path, relative_path)
                print(f"   Added: {relative_path}")

    print(f"✅ Created {zip_filename} with correct HACS structure")
    return zip_filename


def check_git_status():
    """Check if git repository is clean."""
    status = run_command("git status --porcelain")
    return len(status) == 0


def commit_and_tag(version):
    """Commit changes and create git tag."""
    # Add all changes
    run_command("git add .", capture_output=False)

    # Commit
    run_command(f'git commit -m "Release v{version}"', capture_output=False)

    # Create tag
    run_command(f"git tag v{version}", capture_output=False)

    # Push commit and tag
    run_command("git push origin main", capture_output=False)
    run_command(f"git push origin v{version}", capture_output=False)

    print(f"✅ Created git tag v{version} and pushed to GitHub")


def get_change_summary():
    """Get recent changes using reportgen on the latest commit, with fallback."""
    # Check if reportgen is available
    try:
        run_command("which reportgen")
    except:
        print("⚠️  reportgen not found, using default change description")
        return "- Bug fixes and improvements\n- Updated integration components\n- Enhanced stability and performance"

    try:
        # Get the previous commit hash (before version bump)
        commit_hash = run_command("git rev-parse HEAD~1")

        # Run reportgen on the previous commit to see actual changes
        reportgen_output = run_command(f"reportgen {commit_hash}")

        # Extract the change summary section
        lines = reportgen_output.split("\n")
        summary_lines = []
        in_summary = False

        for line in lines:
            if line.strip() == "===== CHANGE SUMMARY =====":
                in_summary = True
                continue
            elif line.strip().startswith("===== ") and in_summary:
                break
            elif in_summary and line.strip():
                # Filter out zip file changes as they're just build artifacts
                line_lower = line.lower()
                if not (
                    ".zip" in line_lower and ("added" in line_lower or "new" in line_lower or "created" in line_lower)
                ):
                    summary_lines.append(line.strip())

        if not summary_lines:
            return "- Bug fixes and improvements\n- Updated integration components"

        return "\n".join(f"- {line}" if not line.startswith("-") else line for line in summary_lines)

    except Exception as e:
        print(f"⚠️  Could not generate change summary: {e}")
        return "- Bug fixes and improvements\n- Updated integration components\n- Enhanced stability and performance"


def create_github_release(version, zip_filename):
    """Create GitHub release with zip file."""
    # Check if gh CLI is authenticated
    try:
        run_command("gh auth status")
    except:
        print("❌ GitHub CLI not authenticated. Please run: gh auth login")
        sys.exit(1)

    # Get recent changes
    change_summary = get_change_summary()

    # Create release notes
    release_notes = f"""Release v{version} - HACS Compatible Integration

## Changes in this Release
{change_summary}

## Installation
Install via HACS or download the `{zip_filename}` file and extract to your `custom_components` folder.
"""

    # Create temporary file for release notes to avoid shell escaping issues
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(release_notes)
        notes_file = f.name

    try:
        # Create release using notes file
        cmd = f'gh release create v{version} {zip_filename} --title "v{version}" --notes-file "{notes_file}"'
        run_command(cmd, capture_output=False)

        print(f"✅ Created GitHub release v{version} with {zip_filename}")
    finally:
        # Clean up temporary file
        os.unlink(notes_file)


def main():
    """Main function."""
    print("🚀 Intelbras Alarm Release Builder")
    print("=" * 40)

    # Check if we're in the right directory
    if not Path("custom_components/intelbras_alarm/manifest.json").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)

    # Get current version
    current_version = get_current_version()
    print(f"📋 Current version: {current_version}")

    # Suggest next versions
    suggestions = suggest_next_version(current_version)
    print("\n🎯 Version options:")
    print(f"   1. Patch: {suggestions['1']} (bug fixes)")
    print(f"   2. Minor: {suggestions['2']} (new features)")
    print(f"   3. Major: {suggestions['3']} (breaking changes)")
    print("   4. Custom version")

    # Get user choice
    while True:
        choice = input("\nSelect option (1-4): ").strip()

        if choice in ["1", "2", "3"]:
            new_version = suggestions[choice]
            break
        elif choice == "4":
            new_version = input("Enter custom version (e.g., 1.3.1): ").strip()
            # Validate version format
            if not re.match(r"^\d+\.\d+\.\d+$", new_version):
                print("❌ Invalid version format. Use x.y.z format.")
                continue
            break
        else:
            print("❌ Invalid choice. Please select 1-4.")

    print(f"\n🎯 Selected version: {new_version}")

    # Confirm
    confirm = input(f"Create release v{new_version}? (y/N): ").strip().lower()
    if confirm != "y":
        print("❌ Release cancelled")
        sys.exit(0)

    print(f"\n🏗️  Building release v{new_version}...")

    try:
        # Update manifest
        update_manifest_version(new_version)

        # Create zip file
        zip_filename = create_hacs_compatible_zip(new_version)

        # Git operations
        commit_and_tag(new_version)

        # Create GitHub release
        create_github_release(new_version, zip_filename)

        print(f"\n🎉 Successfully released v{new_version}!")
        print(f"📦 Release: https://github.com/tarikbc/ha-intelbras-alarm/releases/tag/v{new_version}")
        print(f"💾 Zip file: {zip_filename}")
        print("\n✅ HACS should now be able to install this version correctly!")

    except Exception as e:
        print(f"\n❌ Error during release: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
