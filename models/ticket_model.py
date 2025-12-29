from pydantic import BaseModel, Field
from typing import Optional

class TicketModel(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str
    raised_by: Optional[str] = None
    project_name: str
    assigned_to: Optional[str] = None
    priority: str
    explaination: str
    attachments: Optional[list[str]] = []
    status: Optional[str] = "Pending"