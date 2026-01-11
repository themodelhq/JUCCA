# Simple in-memory session storage for demo
# In production, use Redis or database-backed storage

memory_store = {}

def update_memory(session_id: str, data: dict):
    """Update session memory with new data."""
    if session_id not in memory_store:
        memory_store[session_id] = {}
    memory_store[session_id].update(data)

def get_memory(session_id: str) -> dict:
    """Retrieve session memory."""
    return memory_store.get(session_id, {})

def clear_memory(session_id: str):
    """Clear session memory."""
    if session_id in memory_store:
        del memory_store[session_id]

def get_conversation_history(session_id: str, limit: int = 10) -> list:
    """Get recent conversation history for a session."""
    # This would typically be stored in a database
    return []
