# Medical Receptionist Voice Agent

A production-ready voice agent for medical reception using LiveKit, Sarvam AI, and Groq.

## Tech Stack

- **STT**: Sarvam (saaras:v3) - Speech-to-Text
- **LLM**: Groq (llama-3.3-70b-versatile) - Text Processing
- **TTS**: Sarvam (bulbul:v3) - Text-to-Speech
- **Telephony**: LiveKit + Vobiz SIP Trunk
- **Deployment**: Render + LiveKit Cloud

## Features

- Multilingual support (English + Hindi)
- Real-time voice processing
- Appointment booking assistance
- Call transfer to human agents
- Low latency (~700-1200ms)
- Cost-effective architecture

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_SECRET` - LiveKit API secret
- `SARVAM_API_KEY` - Sarvam API key
- `GROQ_API_KEY` - Groq API key

### 3. Run Agent Locally

```bash
python agent.py
```

### 4. Deploy to Render

1. Push code to GitHub
2. Create Render web service
3. Add environment variables
4. Deploy

## Architecture

```
Caller (Phone)
    ↓
Vobiz SIP Trunk
    ↓
LiveKit SIP Inbound Trunk
    ↓
LiveKit Room
    ↓
Agent Server (Render)
    ├─ Sarvam STT
    ├─ Groq LLM
    └─ Sarvam TTS
    ↓
Audio back to caller
```

## Configuration

Edit `config.py` to customize:
- System prompt
- Greeting message
- STT/TTS/LLM models
- Transfer number

## Cost

Per 100 calls (~5 min each):
- LiveKit: $5-10
- Sarvam: $1-2
- Groq: $0.50-1
- Render: $0 (free tier)
- **Total: ~$6.50-13**
