import os
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import sarvam, groq, noise_cancellation, silero
from livekit.agents import llm
import config

load_dotenv()

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
    def __init__(self, tools: list) -> None:
        super().__init__(
            instructions=config.SYSTEM_PROMPT,
            tools=tools,
        )


server = AgentServer()

@server.rtc_session(agent_name="inbound-assistant")
async def inbound_agent(ctx: agents.JobContext):
    import logging
    logger = logging.getLogger("inbound-agent")
    logger.info(f"Connecting to room: {ctx.room.name}")
    
    # Initialize function context
    fnc_ctx = TransferFunctions(ctx)

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
        agent=InboundAssistant(tools=list(fnc_ctx.function_tools.values())),
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
    import logging
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(server)
