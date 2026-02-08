# DEUS Project

A voice-controlled AI desktop companion inspired by "The Machine" from *Person of Interest*. Features an animated floating eye overlay and a voice interface that connects to a remote AI agent via WebSocket.

**macOS only** — uses native AppKit/Quartz for the transparent overlay window.

## How It Works

1. An animated eye renders as a transparent always-on-top overlay (602 PNG frames at 30fps)
2. Hold **Right Command** to record audio from your mic
3. Speech is transcribed via Google Gemini STT
4. The transcription is sent to a remote agent (clawdbot) over an SSH-tunneled WebSocket
5. The agent's response is spoken back using Gemini TTS

## Setup

```bash
# Clone
git clone https://github.com/buzagloidan/deus_project.git
cd deus_project

# Create venv and install deps
python3 -m venv deus_venv
source deus_venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your actual values
```

You also need:
- An SSH key configured for your remote server
- A Google Gemini API key
- The animation frames in `deus_frames_transparent/` (602 PNGs)

## Usage

```bash
# Eye animation only
./run_deus.sh

# Full system (eye + voice)
./run_deus_full.sh
```

**Controls:**
- Hold **Right Command** — record
- Release — send to agent & hear response
- **Escape** — quit

## Project Structure

```
deus_eye.py            # Animated transparent eye overlay (AppKit/Quartz)
deus_voice.py          # Simple text-based agent interface
deus_voice_full.py     # Full voice interface (STT → Agent → TTS)
run_deus.sh            # Launch eye only
run_deus_full.sh       # Launch eye + voice
deus_frames_transparent/  # Animation frames (not included in repo)
```

## Disclaimer

This project is provided **for educational and research purposes only**. The author assumes no responsibility or liability for any misuse, damage, or consequences arising from the use of this software. Use at your own risk. By using this project, you agree that the author is not responsible for any actions taken with it.

## License

MIT
