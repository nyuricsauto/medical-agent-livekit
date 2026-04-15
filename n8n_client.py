import httpx
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger("n8n-client")


async def call_n8n_webhook(
    action: str,
    call_id: str,
    patient_name: str,
    patient_phone: str,
    doctor: Optional[str] = None,
    slot: Optional[str] = None,
    old_slot: Optional[str] = None,
    conversation_log: Optional[List[Dict[str, Any]]] = None,
    language: str = "en",
    n8n_webhook_url: str = None
) -> Dict[str, Any]:
    """
    Call n8n webhook to execute backend operations.
    
    Actions:
    - bookAppointment: Create appointment
    - cancelAppointment: Delete appointment
    - rescheduleAppointment: Modify existing appointment
    - end-of-call-report: Log call summary
    
    Args:
        action: The action to perform (bookAppointment, cancelAppointment, rescheduleAppointment, end-of-call-report)
        call_id: Call session ID
        patient_name: Patient's full name
        patient_phone: Patient's phone number
        doctor: Selected doctor (optional)
        slot: Selected time slot (optional)
        old_slot: Old time slot for reschedule (optional)
        conversation_log: Conversation history (optional)
        language: Detected language code
        n8n_webhook_url: n8n webhook URL
    
    Returns:
        Response dictionary from n8n
    """
    try:
        webhook_url = n8n_webhook_url
        
        # Build tool call arguments based on action
        arguments = {
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "doctor_name": doctor,
            "appointment_datetime": slot,
        }
        
        if action == "rescheduleAppointment":
            arguments["old_datetime"] = old_slot
            arguments["new_datetime"] = slot
        
        # Build payload in the format expected by the workflow
        payload = {
            "body": {
                "message": {
                    "toolCallList": [
                        {
                            "function": {
                                "name": action,
                                "arguments": arguments
                            },
                            "id": f"tc_{datetime.now().timestamp()}"
                        }
                    ],
                    "call": {
                        "id": call_id,
                        "customer": {
                            "number": patient_phone
                        }
                    },
                    "type": "end-of-call-report" if action == "end-of-call-report" else "tool_call"
                }
            }
        }
        
        # Add call logging data if it's an end-of-call-report
        if action == "end-of-call-report" and conversation_log:
            payload["body"]["message"]["startedAt"] = conversation_log[0].get("timestamp", datetime.now().isoformat()) if conversation_log else datetime.now().isoformat()
            payload["body"]["message"]["endedAt"] = datetime.now().isoformat()
            payload["body"]["message"]["durationSeconds"] = 0
            payload["body"]["message"]["summary"] = conversation_log[-1].get("content", "") if conversation_log else ""
            payload["body"]["message"]["transcript"] = json.dumps(conversation_log) if conversation_log else ""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"n8n {action} result: {result}")
            
            # Parse response format: { results: [{ toolCallId, result }] }
            if "results" in result and len(result["results"]) > 0:
                return {
                    "status": "success",
                    "message": result["results"][0].get("result", ""),
                    "tool_call_id": result["results"][0].get("toolCallId")
                }
            
            return result
    
    except httpx.HTTPError as e:
        logger.error(f"n8n webhook error for {action}: {e}")
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError as e:
        logger.error(f"n8n JSON decode error for {action}: {e}")
        return {"status": "error", "message": "Invalid JSON response"}
    except Exception as e:
        logger.error(f"n8n unexpected error for {action}: {e}")
        return {"status": "error", "message": str(e)}


async def log_final_summary(
    call_id: str,
    patient_name: str,
    patient_phone: str,
    conversation_log: List[Dict[str, Any]],
    n8n_webhook_url: str
) -> Dict[str, Any]:
    """
    Log final conversation summary and close call.
    
    Args:
        call_id: Call session ID
        patient_name: Patient's full name
        patient_phone: Patient's phone number
        conversation_log: Conversation history
        n8n_webhook_url: n8n webhook URL
    
    Returns:
        Response from n8n webhook
    """
    return await call_n8n_webhook(
        action="end-of-call-report",
        call_id=call_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        conversation_log=conversation_log,
        n8n_webhook_url=n8n_webhook_url
    )


async def book_appointment(
    call_id: str,
    patient_name: str,
    patient_phone: str,
    doctor: str,
    slot: str,
    n8n_webhook_url: str
) -> Dict[str, Any]:
    """
    Book a new appointment via n8n.
    
    Args:
        call_id: Call session ID
        patient_name: Patient's full name
        patient_phone: Patient's phone number
        doctor: Selected doctor
        slot: Selected time slot
        n8n_webhook_url: n8n webhook URL
    
    Returns:
        Response with appointment_id and confirmation message
    """
    return await call_n8n_webhook(
        action="bookAppointment",
        call_id=call_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        doctor=doctor,
        slot=slot,
        n8n_webhook_url=n8n_webhook_url
    )


async def reschedule_appointment(
    call_id: str,
    patient_name: str,
    patient_phone: str,
    old_slot: str,
    new_slot: str,
    n8n_webhook_url: str
) -> Dict[str, Any]:
    """
    Reschedule an existing appointment via n8n.
    
    Args:
        call_id: Call session ID
        patient_name: Patient's full name
        patient_phone: Patient's phone number
        old_slot: Old time slot
        new_slot: New time slot
        n8n_webhook_url: n8n webhook URL
    
    Returns:
        Response with updated appointment details
    """
    return await call_n8n_webhook(
        action="rescheduleAppointment",
        call_id=call_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        old_slot=old_slot,
        slot=new_slot,
        n8n_webhook_url=n8n_webhook_url
    )


async def cancel_appointment(
    call_id: str,
    patient_name: str,
    patient_phone: str,
    slot: str,
    n8n_webhook_url: str
) -> Dict[str, Any]:
    """
    Cancel an appointment via n8n.
    
    Args:
        call_id: Call session ID
        patient_name: Patient's full name
        patient_phone: Patient's phone number
        slot: Time slot to cancel
        n8n_webhook_url: n8n webhook URL
    
    Returns:
        Response with cancellation confirmation
    """
    return await call_n8n_webhook(
        action="cancelAppointment",
        call_id=call_id,
        patient_name=patient_name,
        patient_phone=patient_phone,
        slot=slot,
        n8n_webhook_url=n8n_webhook_url
    )
