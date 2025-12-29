from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ChatMessage(BaseModel):
    project_id: int
    receiver_email: str
    message: str

class ChatResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
