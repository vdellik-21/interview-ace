#!/bin/bash
# ═══════════════════════════════════════════
# InterviewAce — macOS Audio Setup
# Installs BlackHole and configures Multi-Output Device
# Run once before first use
# ═══════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🎙️ InterviewAce — macOS Audio Setup${NC}"
echo ""

# Step 1: Check if Homebrew is installed
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}Homebrew not found. Please install it first:${NC}"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

# Step 2: Install BlackHole
echo -e "${BLUE}[1/3] Installing BlackHole 2ch...${NC}"
if brew list blackhole-2ch &>/dev/null; then
    echo "  BlackHole 2ch is already installed ✓"
else
    brew install blackhole-2ch
    echo "  BlackHole 2ch installed ✓"
fi

# Step 3: Instructions for Multi-Output Device
echo ""
echo -e "${BLUE}[2/3] Manual step — Create a Multi-Output Device:${NC}"
echo ""
echo "  1. Open 'Audio MIDI Setup' (search in Spotlight: ⌘+Space → 'Audio MIDI Setup')"
echo "  2. Click the '+' button at the bottom left"
echo "  3. Select 'Create Multi-Output Device'"
echo "  4. Check BOTH:"
echo "     ✓ Built-in Output (your speakers or headphones)"
echo "     ✓ BlackHole 2ch"
echo "  5. Right-click the new device → 'Use This Device For Sound Output'"
echo ""
echo "  This makes the interviewer's audio go to BOTH your ears AND our app."
echo ""

# Step 4: Verify
echo -e "${BLUE}[3/3] Verifying audio devices...${NC}"
echo ""
python3 -c "
import sounddevice as sd
devices = sd.query_devices()
print('Available input devices:')
for i, d in enumerate(devices):
    if d.get('max_input_channels', 0) > 0:
        marker = ' ← USE THIS' if 'blackhole' in d['name'].lower() else ''
        print(f'  [{i}] {d[\"name\"]}{marker}')
" 2>/dev/null || echo "  (Install Python deps first: pip install sounddevice)"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}  ${NC}"
echo -e "${GREEN}  In your .env file, set:${NC}"
echo -e "${GREEN}    SYSTEM_AUDIO_DEVICE=BlackHole 2ch${NC}"
echo -e "${GREEN}    MIC_DEVICE=MacBook Pro Microphone${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
