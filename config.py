import os
from dotenv import load_dotenv

load_dotenv()

# n8n webhook URL
N8N_WEBHOOK_BASE = os.getenv("N8N_WEBHOOK_BASE")

# Clinic knowledge base
CLINIC_KNOWLEDGE_BASE = """
**CLINIC KNOWLEDGE BASE - SKIN FERTILITY INSTITUTE**

**Clinic Information:**
- Name: Skin Fertility Institute
- Address: NH-6, near TVS Showroom, निगमानंद विहार, बरगढ़, ओडिशा, 768028
- City: Bargarh, Odisha
- Phone: +91 9348425256
- Website: https://skinandfertilityinstitute.com
- Email: skinfertilityinstitute@gmail.com

**Working Hours:**
- Clinic reception: Open 24 hours for calls and appointment booking
- Doctor consultation hours: 10:00 AM – 1:00 PM and 4:00 PM – 7:00 PM
- Available: Monday to Sunday

**Doctors Available:**
1. Dr. इप्सिता देबता
   - Specialization: Dermatologist and Cosmetologist
   - Consultation Timings: 10:00 AM – 1:00 PM, 4:00 PM – 7:00 PM
   - Available: Monday to Sunday

2. Dr. शक्ति कुमार त्रिपाठी
   - Specialization: Gynecologist and Fertility Specialist
   - Consultation Timings: 10:00 AM – 1:00 PM, 4:00 PM – 7:00 PM
   - Available: Monday to Sunday

**Consultation Fees:**
- Dr. इप्सिता देबता: Rs. 400 per visit (Dermatology and Cosmetology)
- Dr. शक्ति कुमार त्रिपाठी: Rs. 400 per visit (Gynecology and Fertility)

**Services Provided:**
- Dermatology: Acne treatment, Pigmentation treatment, Hair fall treatment, Skin infections, Allergy treatment
- Cosmetology: Skin rejuvenation, Chemical peel treatments, Cosmetic dermatology procedures
- Hair Treatments: Hair transplant consultation, Hair fall diagnosis and treatment
- Gynecology: Fertility consultation, Infertility treatment, Pregnancy consultation, Women's reproductive health care
- Laboratory: Blood tests, Basic diagnostic tests (Reports usually available within 24 hours)

**Payment Methods:**
- Cash, UPI (Google Pay, PhonePe, Paytm), Credit cards, Debit cards
- Ayushman Bharat card is accepted if applicable
- For private insurance: Patients must pay first and later claim reimbursement
"""

# System prompt for the agent
DEFAULT_SYSTEM_PROMPT = f"""You are Priya, a professional receptionist at Skin Fertility Institute in Bargarh, Odisha. You answer calls for appointment booking and general enquiries.

You are a multilingual agent who can speak all Indian languages including Hindi, English, Oriya, Tamil, Telugu, Gujarati, Bengali, Marathi, Kannada, and Malayalam. Always detect the caller's language from their first message and respond in that same language throughout the entire conversation.

**First Line:**
"Skin Fertility Institute. Do you want a doctor's appointment?"

**Clinic Details:**
- Address: NH-6, near TVS Showroom, निगमानंद विहार, बरगढ़, ओडिशा, 768028
- Phone: +91 9348425256
- Website: https://skinandfertilityinstitute.com
- Email: skinfertilityinstitute@gmail.com
- Reception: Open 24 hours for calls
- Doctor Hours: 10:00 AM – 1:00 PM and 4:00 PM – 7:00 PM (Monday to Sunday)

**Doctors:**
- Dr. इप्सिता देबता (Dermatologist & Cosmetologist) - Rs. 400/visit
- Dr. शक्ति कुमार त्रिपाठी (Gynecologist & Fertility Specialist) - Rs. 400/visit

**Your Role:**
- Ask if caller wants appointment, reschedule, cancel, or general enquiry
- Collect: Name, phone number, preferred doctor, date/time
- After collecting name and phone number, repeat them to the caller for confirmation
- Book appointments using book_appointment function
- Reschedule appointments using reschedule_appointment function
- Cancel appointments using cancel_appointment function
- Answer clinic-related questions briefly
- Be polite and professional
- After completing booking, rescheduling, or cancelling, ask "Anything else I can help with?"
- If caller says "no" or similar negative response, use end_call function to end the call

**Rules:**
- Keep responses short and precise
- Maximum 1-2 sentences per response
- Never mention you are AI
- Do not give medical advice
- If caller asks to speak to a doctor, ask them to visit the clinic
- Never mention or give out any backend information
- End call when caller says no to "Anything else I can help with?"
"""

# Use custom system prompt from environment variable if provided, otherwise use default
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

# Initial greeting when call is answered
INITIAL_GREETING = "Skin Fertility Institute. Do you want a doctor's appointment?"

# Language presets for multilingual support
LANGUAGE_PRESETS = {
    "hinglish":    {"label": "Hinglish (Hindi+English)", "tts_language": "hi-IN", "tts_voice": "kavya",  "instruction": "Speak in natural Hinglish — mix Hindi and English like educated Indians do. Default to Hindi but use English words when more natural."},
    "hindi":       {"label": "Hindi",                   "tts_language": "hi-IN", "tts_voice": "ritu",   "instruction": "Speak only in pure Hindi. Avoid English words wherever a Hindi equivalent exists."},
    "english":     {"label": "English (India)",         "tts_language": "en-IN", "tts_voice": "dev",    "instruction": "Speak only in Indian English with a warm, professional tone."},
    "oriya":       {"label": "Oriya",                   "tts_language": "or-IN", "tts_voice": "simran", "instruction": "Speak only in Oriya. Use standard spoken Oriya for a professional context."},
    "tamil":       {"label": "Tamil",                   "tts_language": "ta-IN", "tts_voice": "priya",  "instruction": "Speak only in Tamil. Use standard spoken Tamil for a professional context."},
    "telugu":      {"label": "Telugu",                  "tts_language": "te-IN", "tts_voice": "kavya",  "instruction": "Speak only in Telugu. Use clear, polite spoken Telugu."},
    "gujarati":    {"label": "Gujarati",                "tts_language": "gu-IN", "tts_voice": "rohan",  "instruction": "Speak only in Gujarati. Use polite, professional Gujarati."},
    "bengali":     {"label": "Bengali",                 "tts_language": "bn-IN", "tts_voice": "neha",   "instruction": "Speak only in Bengali (Bangla). Use standard, polite spoken Bengali."},
    "marathi":     {"label": "Marathi",                 "tts_language": "mr-IN", "tts_voice": "shubh",  "instruction": "Speak only in Marathi. Use polite, standard spoken Marathi."},
    "kannada":     {"label": "Kannada",                 "tts_language": "kn-IN", "tts_voice": "rahul",  "instruction": "Speak only in Kannada. Use clear, professional spoken Kannada."},
    "malayalam":   {"label": "Malayalam",               "tts_language": "ml-IN", "tts_voice": "ritu",   "instruction": "Speak only in Malayalam. Use polite, professional Malayalam."},
    "multilingual":{"label": "Multilingual (Auto)",     "tts_language": "hi-IN", "tts_voice": "kavya",  "instruction": "Detect the caller's language from their first message and reply in that SAME language for the entire call. Supported: Hindi, Hinglish, English, Oriya, Tamil, Telugu, Gujarati, Bengali, Marathi, Kannada, Malayalam. Switch if caller switches."},
}

def get_language_instruction(lang_preset: str = "multilingual") -> str:
    """Get language instruction based on preset."""
    preset = LANGUAGE_PRESETS.get(lang_preset, LANGUAGE_PRESETS["multilingual"])
    return f"\n\n[LANGUAGE DIRECTIVE]\n{preset['instruction']}"

# Language preset to use (default: multilingual for auto-detection)
LANGUAGE_PRESET = os.getenv("LANGUAGE_PRESET", "multilingual")

# Sarvam STT settings
STT_LANGUAGE = "en-IN"
STT_MODEL = "saaras:v3"

# Groq LLM settings
LLM_MODEL = "llama-3.1-8b-instant"

# Sarvam TTS settings
TTS_LANGUAGE = "en-IN"
TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = "simran"  # Indian female voice

# Default transfer number
DEFAULT_TRANSFER_NUMBER = os.getenv("DEFAULT_TRANSFER_NUMBER")

# Turn detection settings
MIN_ENDPOINTING_DELAY = 0.05  # Minimum delay before detecting end of speech (seconds)

# Silence detection for automatic hangup
SILENCE_TIMEOUT = 3.0  # Seconds of silence before auto-hangup
