#!/usr/bin/env python3
"""
DEUS Voice Interface - Voice control for clawdbot
Press Fn to talk, release to send
"""

import subprocess
import tempfile
import os
import json
import urllib.request
import urllib.error
import threading
import time

# Configuration - set these in a .env file or as environment variables
VPS_HOST = os.environ.get("DEUS_VPS_HOST", "")
HOOKS_TOKEN = os.environ.get("DEUS_HOOKS_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("DEUS_TELEGRAM_CHAT_ID", "")
SSH_TUNNEL_PORT = int(os.environ.get("DEUS_SSH_TUNNEL_PORT", "18790"))
HOOKS_URL = f"http://127.0.0.1:18789/hooks/agent"
LOCAL_API_URL = f"http://127.0.0.1:{SSH_TUNNEL_PORT}/hooks/agent"


def check_tunnel_exists():
    """Check if SSH tunnel is already running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"ssh.*{SSH_TUNNEL_PORT}.*{VPS_HOST}"],
            capture_output=True
        )
        return result.returncode == 0
    except:
        return False


def setup_ssh_tunnel():
    """Create SSH tunnel to VPS for API access"""
    if check_tunnel_exists():
        print("SSH tunnel already running.")
        return None

    print("Setting up SSH tunnel to VPS...")
    tunnel = subprocess.Popen(
        ["ssh", "-N", "-L", f"{SSH_TUNNEL_PORT}:127.0.0.1:18789", f"root@{VPS_HOST}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)  # Wait for tunnel to establish
    return tunnel


def speech_to_text_macos(audio_file):
    """Use macOS Speech Recognition"""
    # For now, we'll use a simpler approach with the 'say' command for TTS
    # and manual text input for testing
    # Full speech recognition requires SFSpeechRecognizer which needs more setup
    pass


def record_audio_macos(duration=5):
    """Record audio using macOS"""
    print(f"Recording for {duration} seconds...")
    audio_file = tempfile.mktemp(suffix=".wav")

    # Use sox or afrecord for recording
    try:
        subprocess.run([
            "rec", "-q", audio_file, "trim", "0", str(duration)
        ], check=True, timeout=duration + 2)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to afrecord if sox not available
        try:
            subprocess.run([
                "afrecord", "-d", str(duration), "-o", audio_file
            ], check=True, timeout=duration + 2)
        except FileNotFoundError:
            print("No audio recording tool found. Install sox: brew install sox")
            return None

    return audio_file


def send_to_clawdbot(message):
    """Send message to clawdbot via hooks API through SSH tunnel"""
    payload = {
        "message": message,
        "channel": "telegram",
        "to": TELEGRAM_CHAT_ID,
        "deliver": True,
        "name": "DEUS"
    }

    headers = {
        "Authorization": f"Bearer {HOOKS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(LOCAL_API_URL, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('ok'):
                print(f"Message sent! Run ID: {result.get('runId')}")
                return result
            else:
                print(f"Error: {result}")
                return None
    except urllib.error.URLError as e:
        print(f"Connection error: {e}")
        print(f"Make sure SSH tunnel is running: ssh -N -L {SSH_TUNNEL_PORT}:127.0.0.1:18789 root@{VPS_HOST}")
        return None


def speak_text(text):
    """Use macOS text-to-speech"""
    # Use a natural voice
    subprocess.run(["say", "-v", "Samantha", text])


def main_interactive():
    """Interactive mode - type messages to send"""
    print("\n" + "="*50)
    print("DEUS Voice Interface")
    print("="*50)
    print("\nType your message and press Enter to send to clawdbot.")
    print("The response will appear in your Telegram chat.")
    print("Type 'quit' to exit.\n")

    # Setup SSH tunnel
    tunnel = setup_ssh_tunnel()

    try:
        while True:
            try:
                message = input("You: ").strip()
                if message.lower() == 'quit':
                    break
                if not message:
                    continue

                print("Sending to clawdbot...")
                result = send_to_clawdbot(message)

                if result:
                    print("✓ Message sent! Check Telegram for response.\n")
                    # Optional: speak confirmation
                    # speak_text("Message sent")

            except KeyboardInterrupt:
                break

    finally:
        print("\nShutting down...")
        tunnel.terminate()
        tunnel.wait()


if __name__ == "__main__":
    main_interactive()
