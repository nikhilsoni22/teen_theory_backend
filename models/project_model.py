from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProjectModel(BaseModel):
    id: int
    title: str
    project_type: str
    project_description: str
    status: str
    created_by_email: str
    assigned_student: Optional[list] = []
    assigned_mentor: Optional[list] = []
    project_counsellor: Optional[str] = None
    milestones: Optional[list] = []
    # tasks: Optional[list] = []
    deliverables_title: Optional[str] = None
    deliverables_type: Optional[str] = None
    due_date: Optional[str] = None
    linked_milestones: Optional[str] = None
    metadata_and_req: Optional[str] = None
    page_limit: Optional[str] = None
    additional_instructions: Optional[str] = None
    allow_multiple_submissions: Optional[bool] = False
    montor_approval: Optional[bool] = False
    counsellor_approval: Optional[bool] = False
    resources_type: Optional[str] = None
    resources_title: Optional[str] = None
    resources_description: Optional[str] = None
    attached_files: Optional[str] = None
    student_visibility: Optional[bool] = True
    mentor_visibility: Optional[bool] = True
    session_type: Optional[str] = None
    purpose: Optional[str] = None
    preferred_time: Optional[str] = None
    duration: Optional[str] = None
    created_at: Optional[datetime] = None

class ProjectResponse(BaseModel):
    success: bool
    message: str
    data: dict
    
    