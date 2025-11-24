#!/bin/bash
###############################################################################
# PHILAB Easy Installer for macOS (Intel and Apple Silicon)
#
# This script provides a one-click installation for PHILAB on macOS.
# It handles dependency installation, virtual environment setup, and app building.
#
# Usage:
#   ./install.sh [options]
#   curl -fsSL https://raw.githubusercontent.com/E-TECH-PLAYTECH/PHILAB/main/install.sh | bash -s -- [options]
#
# Options:
#   --with-phi2    Download and enable real Phi-2 model (~2.7GB)
#   --help, -h     Show help message
###############################################################################

set -e

# Parse command-line arguments
WITH_PHI2=false

for arg in "$@"; do
    case $arg in
        --with-phi2)
            WITH_PHI2=true
            shift
            ;;
        --help|-h)
            echo "PHILAB Installer for macOS"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --with-phi2    Download and enable real Phi-2 model (~2.7GB)"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Install with mock model"
            echo "  $0 --with-phi2              # Install with real Phi-2 model"
            echo "  curl -fsSL https://raw.githubusercontent.com/E-TECH-PLAYTECH/PHILAB/main/install.sh | bash -s -- --with-phi2"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Detect architecture
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    echo -e "${BLUE}Detected Apple Silicon (M1/M2/M3/M4)${NC}"
    PYTHON_CMD="python3"
    CONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
elif [[ "$ARCH" == "x86_64" ]]; then
    echo -e "${BLUE}Detected Intel Mac${NC}"
    PYTHON_CMD="python3"
    CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
else
    echo -e "${RED}Unsupported architecture: $ARCH${NC}"
    exit 1
fi

# Check macOS version
MACOS_VERSION=$(sw_vers -productVersion | cut -d. -f1)
if [[ $MACOS_VERSION -lt 12 ]]; then
    echo -e "${YELLOW}Warning: macOS $MACOS_VERSION detected. PHILAB requires macOS 12+ for best performance.${NC}"
fi

echo -e "${GREEN}Starting PHILAB installation...${NC}"

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo -e "${BLUE}Installing Homebrew...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)"
fi

# Install Python if not present
if ! command -v python3 &> /dev/null; then
    echo -e "${BLUE}Installing Python 3.11...${NC}"
    brew install python@3.11
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2 | cut -d. -f1-2)
if [[ $(echo "$PYTHON_VERSION < 3.10" | bc -l) -eq 1 ]]; then
    echo -e "${RED}Python $PYTHON_VERSION is too old. Installing Python 3.11...${NC}"
    brew install python@3.11
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
fi

# Create virtual environment
echo -e "${BLUE}Setting up virtual environment...${NC}"
VENV_DIR="$HOME/.philab"
$PYTHON_CMD -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Clone or download PHILAB
if [[ ! -d "$HOME/PHILAB" ]]; then
    echo -e "${BLUE}Downloading PHILAB...${NC}"
    git clone https://github.com/E-TECH-PLAYTECH/PHILAB.git "$HOME/PHILAB"
else
    echo -e "${BLUE}Updating PHILAB...${NC}"
    cd "$HOME/PHILAB"
    git pull
fi

cd "$HOME/PHILAB"

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install -e .

# Install optional ML dependencies
echo -e "${YELLOW}Installing ML dependencies (this may take a while)...${NC}"
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate

# Create desktop shortcut
echo -e "${BLUE}Creating desktop shortcuts...${NC}"
cat > "$HOME/Desktop/PHILAB.command" << 'EOF'
#!/bin/bash
source "$HOME/.philab/bin/activate"
cd "$HOME/PHILAB"
python -m phi2_lab.geometry_viz.api &
sleep 2
open http://127.0.0.1:8000
EOF
chmod +x "$HOME/Desktop/PHILAB.command"

# Create Applications symlink
if [[ -d "/Applications" ]]; then
    ln -sf "$HOME/Desktop/PHILAB.command" "/Applications/PHILAB"
fi

# Enable Phi-2 if requested
if [ "$WITH_PHI2" = true ]; then
    echo -e "${BLUE}Enabling Phi-2 model...${NC}"
    ./enable-phi2.sh
    echo ""
fi

echo -e "${GREEN}Installation complete!${NC}"
echo -e "${BLUE}To run PHILAB:${NC}"
echo "1. Double-click PHILAB.command on your Desktop"
echo "2. Or run: source ~/.philab/bin/activate && cd ~/PHILAB && python -m phi2_lab.geometry_viz.api"
echo ""
echo -e "${YELLOW}Note: First run may download model weights.${NC}"</content>
<parameter name="filePath">/Users/magus/Desktop/PHILAB_GROK/PHILAB/install.sh