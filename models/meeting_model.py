from pydantic import BaseModel, Field
from typing import Optional, List, Union


class MeetingModel(BaseModel):
    id: str = Field(..., alias="_id")
    project_name: Optional[str] = None
    link_created_by: Optional[str] = None
    title: str
    date_time: str
    meeting_link: str
    status: Optional[str] = "pending"
    project_counsellor_email: Optional[str] = None
    project_mentor: Optional[dict] = None


class MentorMeetings(BaseModel):
    meeting_type: str
    # Accept either a single string or a list of strings for assigned students
    assigned_students: Optional[Union[str, List[str]]] = None
    date_time: str
    duration: str
    purpose: Optional[str] = None
    meeting_link: str

    class Config:
        # allow population by field name so clients sending lower-case keys work
        allow_population_by_field_name = True