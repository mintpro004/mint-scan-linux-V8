#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — COMPREHENSIVE UPDATER                      ║
# ║   Works: GitHub pull · Offline self-heal · Package update   ║
# ╚══════════════════════════════════════════════════════════════╝
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   MINT SCAN v8 — COMPREHENSIVE UPDATER                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# [1] Fix ownership
echo -e "${YELLOW}[1/4] Fixing ownership...${NC}"
sudo chown -R "$USER:$USER" "$SCRIPT_DIR" 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
echo -e "${GREEN}  ✓ Done${NC}"

# [2] Try GitHub pull — gracefully skip if no internet / not a git repo
echo -e "${YELLOW}[2/4] Checking for GitHub updates...${NC}"
PULLED=false

if [ -d ".git" ]; then
    # Test connectivity first (2s timeout)
    if curl -s --connect-timeout 2 https://github.com > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Internet available — pulling from GitHub...${NC}"
        # Stash local changes so pull can proceed
        if [[ $(git status --porcelain) ]]; then
            echo -e "  ${YELLOW}Stashing local changes...${NC}"
            git stash -u > /dev/null 2>&1 || true
            STASHED=true
        fi

        if git pull --rebase origin main 2>/dev/null; then
            echo -e "  ${GREEN}✓ GitHub pull successful${NC}"
            PULLED=true
        else
            echo -e "  ${YELLOW}  Pull failed (possible conflict) — continuing with local files${NC}"
        fi

        # Re-apply stashed changes
        if [ "${STASHED:-false}" = true ]; then
            git stash pop > /dev/null 2>&1 || true
        fi
    else
        echo -e "  ${YELLOW}  No internet connection — skipping GitHub pull${NC}"
        echo -e "  ${YELLOW}  Running offline self-heal only${NC}"
    fi
else
    echo -e "  ${YELLOW}  Not a git repository — running offline self-heal only${NC}"
    echo -e "  ${YELLOW}  To use GitHub updates: git clone https://github.com/mintpro004/mint-scan-linux.git${NC}"
fi

# [3] Update Python packages
echo -e "${YELLOW}[3/4] Updating Python packages...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null
    pip install -q --upgrade pip 2>/dev/null
    pip install -q --upgrade customtkinter requests psutil netifaces pillow darkdetect 2>/dev/null || true
    echo -e "${GREEN}  ✓ Python packages updated${NC}"
else
    echo -e "  ${YELLOW}  venv not found — full install will rebuild it${NC}"
fi

# [4] Run self-healing installer
echo -e "${YELLOW}[4/4] Running self-healing installer...${NC}"
bash install.sh

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
[ "$PULLED" = true ] && \
echo "║  ✓ GitHub update applied                                    ║"
echo "║  ✓ Packages updated                                         ║"
echo "║  ✓ Self-heal complete                                       ║"
echo "║  Run: bash run.sh                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
