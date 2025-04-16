

import datetime


class ChatState:
    project_id: str
    user_id: str
    state: dict
    datetime: str

    def __init__(self, project_id: str, user_id: str):
        self.project_id = project_id
        self.user_id = user_id
        self.state = {}
        self.datetime = datetime.datetime.now()

    def to_json(self):
        return {
            "project_id": self.project_id,
            "user_id": self.user_id,
            "state": self.state
        }
