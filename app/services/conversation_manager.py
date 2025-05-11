class ConversationManager:
    def __init__(self):
        self.sessions = {}

    def add_message(self, session_id: str, role: str, message: str):
        self.sessions.setdefault(session_id, {"history": [], "attributes": {}})
        self.sessions[session_id]["history"].append({"role": role, "content": message})

    def get_history(self, session_id: str):
        return self.sessions.get(session_id, {}).get("history", [])

    def set_attribute(self, session_id: str, key: str, value):
        self.sessions.setdefault(session_id, {"history": [], "attributes": {}})
        self.sessions[session_id]["attributes"][key] = value

    def get_attribute(self, session_id: str, key: str):
        return self.sessions.get(session_id, {}).get("attributes", {}).get(key)
