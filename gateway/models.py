from pydantic import BaseModel


class NotificationRequest(BaseModel):
    email: str
    message: str
