#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — UPDATER  (git pull only)                   ║
# ║   Repository: github.com/mintpro004/mint-scan-linux-V8      ║
# ╚══════════════════════════════════════════════════════════════╝
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   MINT SCAN v8 — UPDATER                                    ║"
echo "║   Repository: github.com/mintpro004/mint-scan-linux-V8      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Must be a git repo
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo -e "${RED}ERROR: Not a git repository.${NC}"
    echo ""
    echo "Mint Scan v8 must be installed via git clone:"
    echo -e "  ${CYAN}git clone https://github.com/mintpro004/mint-scan-linux-V8.git ~/mint-scan-linux${NC}"
    echo -e "  ${CYAN}cd ~/mint-scan-linux && bash install.sh && bash run.sh${NC}"
    exit 1
fi

# Show current version
echo -e "${YELLOW}Current installation:${NC}"
echo "  Directory: $SCRIPT_DIR"
echo "  Remote:    $(git remote get-url origin 2>/dev/null || echo 'not configured')"
echo "  Branch:    $(git branch --show-current 2>/dev/null || echo 'unknown')"
echo "  Commit:    $(git log --oneline -1 2>/dev/null || echo 'unknown')"
echo ""

# Fix ownership
echo -e "${YELLOW}[1/4] Fixing ownership...${NC}"
sudo chown -R "$USER:$USER" "$SCRIPT_DIR" 2>/dev/null || true

# Fetch
echo -e "${YELLOW}[2/4] Fetching from GitHub...${NC}"
if ! git fetch origin 2>&1; then
    echo -e "${RED}  ✗ Fetch failed — check internet connection${NC}"
    echo -e "${YELLOW}  Running offline self-heal instead...${NC}"
    bash install.sh
    exit 0
fi

# Show what's new
BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo 0)
if [ "$BEHIND" -eq 0 ]; then
    echo -e "${GREEN}  ✓ Already up to date ($(git log --oneline -1 2>/dev/null))${NC}"
else
    echo -e "${CYAN}  $BEHIND new commit(s) available:${NC}"
    git log HEAD..origin/main --oneline 2>/dev/null | head -10 | sed 's/^/    /'
fi

# Pull
echo -e "${YELLOW}[3/4] Pulling latest...${NC}"
if git pull origin main --rebase 2>&1; then
    echo -e "${GREEN}  ✓ Update complete${NC}"
    echo "  Now at: $(git log --oneline -1 2>/dev/null)"
else
    echo -e "${RED}  ✗ Pull failed — running self-heal${NC}"
    bash install.sh
    exit 0
fi

# Re-run installer to pick up new deps
echo -e "${YELLOW}[4/4] Running installer for new dependencies...${NC}"
bash install.sh

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ✓ Mint Scan v8 updated successfully                       ║"
echo "║   Run: bash run.sh                                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
