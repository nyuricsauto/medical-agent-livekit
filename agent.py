import os
import time
import asyncio
from dotenv import load_dotenv
from livekit import agents, rtc, api
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import sarvam, groq, noise_cancellation, silero
from livekit.agents import llm
import config
from n8n_client import book_appointment, reschedule_appointment, cancel_appointment, log_final_summary
import logging
from datetime import datetime

load_dotenv()

logger = logging.getLogger("inbound-agent")

class SessionState:
    """Track conversation state across the call."""
    def __init__(self):
        self.patient_name = None
        self.patient_phone = None
        self.conversation_history = []
        self.call_id = None

    def add_turn(self, role: str, content: str):
        """Add a conversation turn."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })


class AppointmentFunctions(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, session_state: SessionState):
        super().__init__(tools=[])
        self.ctx = ctx
        self.session_state = session_state

    @llm.function_tool(description="Book a new appointment. Requires patient_name, patient_phone, doctor, and slot in YYYY-MM-DD HH:MM format.")
    async def book_appointment(self, patient_name: str, patient_phone: str, doctor: str, slot: str):
        """
        Book a new appointment via n8n.
        """
        logger.info(f"Booking appointment for {patient_name} with {doctor} at {slot}")
        
        # Update session state
        self.session_state.patient_name = patient_name
        self.session_state.patient_phone = patient_phone
        
        # Call n8n
        result = await book_appointment(
            call_id=self.session_state.call_id or self.ctx.room.name,
            patient_name=patient_name,
            patient_phone=patient_phone,
            doctor=doctor,
            slot=slot,
            n8n_webhook_url=config.N8N_WEBHOOK_BASE
        )
        
        if result.get("status") == "success":
            return f"Appointment booked successfully for {patient_name} with {doctor} at {slot}. Confirmation: {result.get('message')}"
        else:
            return f"Failed to book appointment: {result.get('message')}"

    @llm.function_tool(description="Reschedule an existing appointment. Requires patient_name, patient_phone, old_slot, and new_slot in YYYY-MM-DD HH:MM format.")
    async def reschedule_appointment(self, patient_name: str, patient_phone: str, old_slot: str, new_slot: str):
        """
        Reschedule an existing appointment via n8n.
        """
        logger.info(f"Rescheduling appointment for {patient_name} from {old_slot} to {new_slot}")
        
        result = await reschedule_appointment(
            call_id=self.session_state.call_id or self.ctx.room.name,
            patient_name=patient_name,
            patient_phone=patient_phone,
            old_slot=old_slot,
            new_slot=new_slot,
            n8n_webhook_url=config.N8N_WEBHOOK_BASE
        )
        
        if result.get("status") == "success":
            return f"Appointment rescheduled successfully from {old_slot} to {new_slot}. Confirmation: {result.get('message')}"
        else:
            return f"Failed to reschedule appointment: {result.get('message')}"

    @llm.function_tool(description="Cancel an existing appointment. Requires patient_name, patient_phone, and slot in YYYY-MM-DD HH:MM format.")
    async def cancel_appointment(self, patient_name: str, patient_phone: str, slot: str):
        """
        Cancel an appointment via n8n.
        """
        logger.info(f"Cancelling appointment for {patient_name} at {slot}")
        
        result = await cancel_appointment(
            call_id=self.session_state.call_id or self.ctx.room.name,
            patient_name=patient_name,
            patient_phone=patient_phone,
            slot=slot,
            n8n_webhook_url=config.N8N_WEBHOOK_BASE
        )
        
        if result.get("status") == "success":
            return f"Appointment cancelled successfully for {patient_name} at {slot}. Confirmation: {result.get('message')}"
        else:
            return f"Failed to cancel appointment: {result.get('message')}"

    @llm.function_tool(description="End the call. Use this when the caller says no to 'anything else I can help with' or when the conversation is complete.")
    async def end_call(self):
        """
        End the call by disconnecting the SIP participant.
        """
        logger.info("Ending call via end_call function")
        
        # Find the SIP participant and disconnect
        for p in self.ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                await self.ctx.room.disconnect_participant(p.identity)
                logger.info(f"Disconnected SIP participant: {p.identity}")
                return "Call ended. Thank you for calling Skin Fertility Institute."
        
        return "Unable to end call - no SIP participant found."


class TransferFunctions(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext):
        super().__init__(tools=[])
        self.ctx = ctx

    @llm.function_tool(description="Transfer the call to a human support agent or another phone number.")
    async def transfer_call(self, destination: str = None):
        """
        Transfer the call to a human.
        """
        if destination is None:
            destination = config.DEFAULT_TRANSFER_NUMBER
            if not destination:
                return "Error: No default transfer number configured."
        
        logger.info(f"Transferring call to {destination}")
        
        # Find the SIP participant to transfer
        participant_identity = None
        for p in self.ctx.room.remote_participants.values():
            if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                participant_identity = p.identity
                break
        
        if not participant_identity:
            logger.error("Could not find SIP participant to transfer")
            return "Failed to transfer: could not identify the caller."

        try:
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=participant_identity,
                    transfer_to=destination,
                    play_dialtone=False
                )
            )
            return "Transfer initiated successfully."
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return f"Error executing transfer: {e}"


class InboundAssistant(Agent):
    """
    An AI agent for inbound medical reception calls.
    """
    def __init__(self, session_state: SessionState, tools: list) -> None:
        # Get language instruction based on preset
        language_instruction = config.get_language_instruction(config.LANGUAGE_PRESET)
        # Combine system prompt with language instruction
        instructions = config.SYSTEM_PROMPT + language_instruction
        
        super().__init__(
            instructions=instructions,
            tools=tools,
        )
        self.session_state = session_state


server = AgentServer()

@server.rtc_session(agent_name="inbound-assistant")
async def inbound_agent(ctx: agents.JobContext):
    await ctx.connect()
    logger.info(f"Connecting to room: {ctx.room.name}")

    # Initialize session state
    session_state = SessionState()
    session_state.call_id = ctx.room.name
    
    # Initialize function contexts
    appt_fnc = AppointmentFunctions(ctx, session_state)
    transfer_fnc = TransferFunctions(ctx)
    
    # Combine all tools
    all_tools = list(appt_fnc.function_tools.values()) + list(transfer_fnc.function_tools.values())
    
    # Silence detection variables
    last_speech_time = time.time()
    silence_check_task = None
    silence_enabled = False  # Only start counting after first agent greeting finishes

    async def check_silence():
        """Background task to check for silence and auto-hangup."""
        nonlocal last_speech_time, silence_enabled
        while True:
            await asyncio.sleep(1)
            if not silence_enabled:
                continue
            if time.time() - last_speech_time > config.SILENCE_TIMEOUT:
                logger.info(f"Silence timeout ({config.SILENCE_TIMEOUT}s) reached, ending call")
                for p in ctx.room.remote_participants.values():
                    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
                        await ctx.room.disconnect_participant(p.identity)
                        logger.info(f"Auto-ended call due to silence: {p.identity}")
                        return
                break

    # Initialize the Agent Session with plugins
    session = AgentSession(
        stt=sarvam.STT(
            language=config.STT_LANGUAGE,
            model=config.STT_MODEL,
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        ),
        llm=groq.LLM(
            model=config.LLM_MODEL,
        ),
        tts=sarvam.TTS(
            target_language_code=config.TTS_LANGUAGE,
            model=config.TTS_MODEL,
            speaker=config.TTS_SPEAKER,
            speech_sample_rate=24000,
        ),
        vad=silero.VAD.load(),
        turn_detection="stt",
        min_endpointing_delay=config.MIN_ENDPOINTING_DELAY,
        allow_interruptions=True,
    )
    
    # Reset timer when user speaks
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        nonlocal last_speech_time
        last_speech_time = time.time()
        logger.debug(f"User speech detected, updated last_speech_time")

    # Reset timer after agent finishes speaking; enable silence check after first greeting
    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        nonlocal last_speech_time, silence_enabled
        last_speech_time = time.time()
        silence_enabled = True
        logger.debug(f"Agent speech committed, silence detection active")

    # Start the session
    await session.start(
        room=ctx.room,
        agent=InboundAssistant(session_state, all_tools),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params:
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC(),
            ),
        ),
    )

    # Generate initial greeting
    await session.generate_reply(instructions=config.INITIAL_GREETING)

    # Start silence detection task
    silence_check_task = asyncio.create_task(check_silence())
    logger.info("Agent started and greeting sent")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(server)
