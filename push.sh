#!/bin/bash
# Mint Scan — GitHub Update Helper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\033[0;36m[ MINT SCAN ]\033[0m Preparing update for GitHub..."

# Add all changes
git add .

# Prompt for commit message or use default
MSG="v8.2: World-Standard Security Hardening, Shell Injection Protection, and UI Reorganization"
if [ -n "$1" ]; then
    MSG="$1"
fi

echo -e "\033[0;36m[ MINT SCAN ]\033[0m Committing changes..."
git commit -m "$MSG"

echo -e "\033[0;36m[ MINT SCAN ]\033[0m Pushing to main branch..."
if git push origin main; then
    echo -e "\033[0;32m[ MINT SCAN ]\033[0m Successfully updated GitHub!"
else
    echo -e "\033[0;31m[ MINT SCAN ]\033[0m Push failed. Check your internet or GitHub permissions."
fi
