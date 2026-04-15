import os
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
        super().__init__(
            instructions=config.SYSTEM_PROMPT,
            tools=tools,
        )
        self.session_state = session_state


server = AgentServer()

@server.rtc_session(agent_name="inbound-assistant")
async def inbound_agent(ctx: agents.JobContext):
    logger.info(f"Connecting to room: {ctx.room.name}")
    
    # Initialize session state
    session_state = SessionState()
    session_state.call_id = ctx.room.name
    
    # Initialize function contexts
    appt_fnc = AppointmentFunctions(ctx, session_state)
    transfer_fnc = TransferFunctions(ctx)
    
    # Combine all tools
    all_tools = list(appt_fnc.function_tools.values()) + list(transfer_fnc.function_tools.values())

    # Initialize the Agent Session with plugins
    session = AgentSession(
        stt=sarvam.STT(
            language=config.STT_LANGUAGE,
            model=config.STT_MODEL,
        ),
        llm=groq.LLM(
            model=config.LLM_MODEL,
        ),
        tts=sarvam.TTS(
            target_language_code=config.TTS_LANGUAGE,
            model=config.TTS_MODEL,
            speaker=config.TTS_SPEAKER,
        ),
        vad=silero.VAD.load(),
    )

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
    
    logger.info("Agent started and greeting sent")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(server)
