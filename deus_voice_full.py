#!/usr/bin/env python3
"""
DEUS Voice Interface - Full voice control with ElevenLabs
Press and hold Option+Space to talk, release to send
"""

import subprocess
import threading
import queue
import time
import json
import urllib.request
import urllib.error
import tempfile
import os
import wave
import struct
# Audio recording
import pyaudio
import base64

# WebSocket
import websockets

# Keyboard listener
from pynput import keyboard

# Configuration - set these in a .env file or as environment variables
VPS_HOST = os.environ.get("DEUS_VPS_HOST", "")
HOOKS_TOKEN = os.environ.get("DEUS_HOOKS_TOKEN", "")
GATEWAY_TOKEN = os.environ.get("DEUS_GATEWAY_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("DEUS_TELEGRAM_CHAT_ID", "")
SSH_TUNNEL_PORT = int(os.environ.get("DEUS_SSH_TUNNEL_PORT", "18790"))
LOCAL_API_URL = f"http://127.0.0.1:{SSH_TUNNEL_PORT}/hooks/agent"
WS_URL = f"ws://127.0.0.1:{SSH_TUNNEL_PORT}"

# Gemini
GEMINI_API_KEY = os.environ.get("DEUS_GEMINI_API_KEY", "")
GEMINI_STT_MODEL = os.environ.get("DEUS_GEMINI_STT_MODEL", "gemini-2.5-flash-preview-04-17")
GEMINI_TTS_MODEL = os.environ.get("DEUS_GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.environ.get("DEUS_GEMINI_TTS_VOICE", "Charon")

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 1
CHUNK = 1024

# State
is_recording = False
audio_queue = queue.Queue()
rcmd_pressed = False


class AudioRecorder:
    def __init__(self):
        self.frames = []
        self.is_recording = False
        self._lock = threading.Lock()

    def start_recording(self):
        self.frames = []
        self.is_recording = True
        # Create fresh pyaudio instance each time to avoid memory corruption
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        print("🎤 Recording... (release keys to stop)")

        try:
            while self.is_recording:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    self.frames.append(data)
                except:
                    break
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    def stop_recording(self):
        self.is_recording = False
        time.sleep(0.1)  # Give the recording thread time to clean up
        print("⏹️  Recording stopped")
        return list(self.frames)

    def save_wav(self, frames, filename):
        audio = pyaudio.PyAudio()
        sample_width = audio.get_sample_size(pyaudio.paInt16)
        audio.terminate()
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(sample_width)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        return filename


def speech_to_text(audio_file):
    """Convert audio to text using Gemini"""
    try:
        with open(audio_file, 'rb') as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_STT_MODEL}:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": [{
                "parts": [
                    {"text": "You are a strict speech-to-text transcriber. Listen to this audio and output ONLY the exact words spoken. Do not paraphrase, interpret, summarize, or add anything. If nothing is spoken, output exactly: [EMPTY]"},
                    {"inline_data": {"mime_type": "audio/wav", "data": audio_b64}}
                ]
            }],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 500
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method='POST')

        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text and text != "[EMPTY]":
                print(f"📝 You said: {text}")
                return text
            else:
                print("❌ Could not understand audio")
                return None
    except (TimeoutError, OSError) as e:
        print(f"❌ Network timeout: {e}")
        return None
    except Exception as e:
        print(f"❌ Speech recognition error: {e}")
        return None


def send_to_clawdbot(message):
    """Send message to clawdbot via WebSocket and get the response"""
    from websockets.sync.client import connect as ws_connect
    import uuid
    req_id = str(uuid.uuid4())
    connect_id = str(uuid.uuid4())

    try:
        with ws_connect(WS_URL, close_timeout=5) as ws:
            # Step 1: Send connect handshake
            connect_frame = {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "gateway-client",
                        "displayName": "DEUS Voice",
                        "version": "1.0.0",
                        "platform": "macos",
                        "mode": "backend"
                    },
                    "auth": {
                        "token": GATEWAY_TOKEN
                    },
                    "role": "operator",
                    "scopes": ["operator.admin"]
                }
            }
            ws.send(json.dumps(connect_frame))

            # Step 2: Wait for hello-ok
            hello = json.loads(ws.recv(timeout=10))
            if not hello.get("ok", True):
                print(f"❌ WebSocket handshake failed: {hello}")
                return None

            # Step 3: Send agent request
            agent_frame = {
                "type": "req",
                "id": req_id,
                "method": "agent",
                "params": {
                    "message": message,
                    "channel": "telegram",
                    "to": TELEGRAM_CHAT_ID,
                    "deliver": True,
                    "label": "DEUS",
                    "idempotencyKey": req_id
                }
            }
            print("🔄 Sending to clawdbot...")
            ws.send(json.dumps(agent_frame))

            # Step 4: Wait for responses (first=accepted, second=completed with result)
            deadline = time.time() + 120
            while time.time() < deadline:
                try:
                    raw = ws.recv(timeout=5)
                    frame = json.loads(raw)

                    # Skip non-response frames (events, ticks, etc.)
                    if frame.get("type") != "res" or frame.get("id") != req_id:
                        continue

                    # Handle validation/auth errors
                    if not frame.get("ok"):
                        err = frame.get("error", {})
                        print(f"❌ Agent request error: {err.get('message', 'unknown')}")
                        return None

                    payload = frame.get("payload", {})
                    status = payload.get("status")

                    if status == "accepted":
                        run_id = payload.get("runId", "")
                        print(f"✓ Message sent (run: {run_id[:8]}...)")
                        print("⏳ Waiting for clawdbot response...")
                        continue

                    if status == "ok":
                        # Extract the response text from payloads
                        result = payload.get("result", {})
                        payloads = result.get("payloads", [])
                        texts = []
                        for p in payloads:
                            if isinstance(p, dict) and p.get("text"):
                                texts.append(p["text"])
                            elif isinstance(p, str):
                                texts.append(p)
                        response_text = "\n".join(texts) if texts else None
                        if response_text:
                            print(f"💬 Clawdbot: {response_text[:80]}...")
                        return response_text

                    if status == "error":
                        print(f"❌ Agent error: {payload.get('summary', 'unknown')}")
                        return None

                except TimeoutError:
                    continue

            print("⏰ Timed out waiting for response")
            return None

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return None


def speak_gemini(text):
    """Use Gemini TTS to speak text"""
    print(f"🔊 Speaking: {text[:50]}...")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": f"Say the following text out loud: {text}"}]
        }],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": GEMINI_TTS_VOICE
                    }
                }
            }
        }
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            part = result["candidates"][0]["content"]["parts"][0]
            # Handle both possible structures
            if "inline_data" in part:
                audio_b64 = part["inline_data"]["data"]
            elif "inlineData" in part:
                audio_b64 = part["inlineData"]["data"]
            else:
                print(f"❌ Unexpected TTS response: {list(part.keys())}")
                subprocess.run(["say", text])
                return False
            audio_bytes = base64.b64decode(audio_b64)

            # Save as WAV (Gemini TTS returns PCM at 24kHz)
            audio_file = tempfile.mktemp(suffix=".wav")
            with wave.open(audio_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_bytes)

            subprocess.run(["afplay", audio_file], check=True)
            os.remove(audio_file)
            return True
    except Exception as e:
        print(f"❌ Gemini TTS error: {e}")
        subprocess.run(["say", text])
        return False


def speak_macos(text):
    """Fallback: Use macOS text-to-speech"""
    subprocess.run(["say", "-v", "Samantha", text])


# Global recorder
recorder = AudioRecorder()
recording_thread = None


def on_press(key):
    global rcmd_pressed, recording_thread, is_recording

    try:
        if key == keyboard.Key.cmd_r:
            rcmd_pressed = True

        if rcmd_pressed and not is_recording:
            is_recording = True
            recording_thread = threading.Thread(target=recorder.start_recording)
            recording_thread.start()
    except:
        pass


def on_release(key):
    global rcmd_pressed, is_recording, recording_thread

    try:
        if key == keyboard.Key.cmd_r:
            rcmd_pressed = False

        if is_recording and not rcmd_pressed:
            is_recording = False
            frames = recorder.stop_recording()

            if recording_thread:
                recording_thread.join(timeout=1)

            if frames and len(frames) > 10:  # Minimum recording length
                # Process in background
                threading.Thread(target=process_recording, args=(frames,)).start()
            else:
                print("⚠️  Recording too short, try again")

        # Exit on Escape
        if key == keyboard.Key.esc:
            print("\n👋 Goodbye!")
            return False
    except:
        pass


def process_recording(frames):
    """Process recorded audio: STT -> clawdbot -> TTS"""
    # Save audio
    audio_file = tempfile.mktemp(suffix=".wav")
    recorder.save_wav(frames, audio_file)

    # Speech to text
    text = speech_to_text(audio_file)
    os.remove(audio_file)

    if not text:
        speak_gemini("I didn't catch that")
        return

    # Send to clawdbot and get response directly via WebSocket
    reply = send_to_clawdbot(text)

    if reply:
        speak_gemini(reply)
    else:
        speak_gemini("No response received")


def check_ssh_tunnel():
    """Check if SSH tunnel is running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"ssh.*{SSH_TUNNEL_PORT}.*{VPS_HOST}"],
            capture_output=True
        )
        return result.returncode == 0
    except:
        return False


def main():
    print("\n" + "="*50)
    print("  DEUS Voice Interface")
    print("="*50)
    print("\n  Hold Right Command to talk")
    print("  Release to send to clawdbot")
    print("  DEUS will speak the response")
    print("  Press Escape to quit")
    print("\n" + "="*50 + "\n")

    # Check SSH tunnel
    if not check_ssh_tunnel():
        print("⚠️  SSH tunnel not running!")
        print(f"  Run: ssh -f -N -L {SSH_TUNNEL_PORT}:127.0.0.1:18789 root@{VPS_HOST}")
        print()
    else:
        print("✓ SSH tunnel connected\n")

    # Start keyboard listener
    print("🎧 Listening for Right Command...\n")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
