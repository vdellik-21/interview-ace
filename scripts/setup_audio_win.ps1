# ═══════════════════════════════════════════
# InterviewAce — Windows Audio Setup
# Downloads VB-Audio Cable and guides configuration
# Run once before first use (PowerShell)
# ═══════════════════════════════════════════

Write-Host "🎙️ InterviewAce — Windows Audio Setup" -ForegroundColor Green
Write-Host ""

# Step 1: Check if VB-Cable is already installed
$vbCable = Get-WmiObject Win32_SoundDevice | Where-Object { $_.Name -like "*VB-Audio*" }
if ($vbCable) {
    Write-Host "[1/3] VB-Audio Cable is already installed ✓" -ForegroundColor Blue
} else {
    Write-Host "[1/3] VB-Audio Cable not found." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Please download and install VB-Audio Cable:"
    Write-Host "  https://vb-audio.com/Cable/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. Download VBCABLE_Driver_Pack43.zip"
    Write-Host "  2. Extract and run VBCABLE_Setup_x64.exe as Administrator"
    Write-Host "  3. Restart your computer"
    Write-Host ""
    Read-Host "Press Enter after installing VB-Cable..."
}

# Step 2: Configure audio
Write-Host ""
Write-Host "[2/3] Configure Windows audio routing:" -ForegroundColor Blue
Write-Host ""
Write-Host "  1. Open Sound Settings (right-click speaker icon in taskbar)"
Write-Host "  2. Under 'Output', select your normal speakers/headphones"
Write-Host "  3. Open 'Sound Control Panel' (Advanced sound options)"
Write-Host "  4. On the 'Recording' tab, find 'CABLE Output (VB-Audio)'"
Write-Host "  5. Right-click → Set as Default Device"
Write-Host ""
Write-Host "  Alternative: Use 'Stereo Mix' if your sound card supports it"
Write-Host ""

# Step 3: Verify
Write-Host "[3/3] Verifying audio devices..." -ForegroundColor Blue
Write-Host ""
python -c @"
import sounddevice as sd
devices = sd.query_devices()
print('Available input devices:')
for i, d in enumerate(devices):
    if d.get('max_input_channels', 0) > 0:
        marker = ' <-- USE THIS' if 'cable' in d['name'].lower() or 'vb-audio' in d['name'].lower() else ''
        print(f'  [{i}] {d["name"]}{marker}')
"@

Write-Host ""
Write-Host "═══════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  In your .env file, set:" -ForegroundColor Green
Write-Host "    SYSTEM_AUDIO_DEVICE=CABLE Output (VB-Audio Virtual Cable)" -ForegroundColor Green
Write-Host "    MIC_DEVICE=Microphone (your headset/mic name)" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════" -ForegroundColor Green
