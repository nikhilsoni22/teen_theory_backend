from pydantic import BaseModel, EmailStr
from typing import Optional, Union
from datetime import datetime

class CreateUserModel(BaseModel):
    user_role: str
    full_name: str
    email: EmailStr
    password: str
    child: Optional[Union[str, dict]] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    profile_photo: Optional[str] = None
    about_me: Optional[str] = None
    total_students: Optional[int] = 0
    total_sessions: Optional[int] = 0
    rating: Optional[float] = 0.0
    exp: Optional[str] = None
    expertise: Optional[list] = []
    certificate: Optional[list] = []
    active_projects: Optional[int] = 0
    completed_projects: Optional[int] = 0
    achievements: Optional[list] = []
    age: Optional[int] = None
    school: Optional[str] = None
    dob: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_contact: Optional[str] = None
    cgpa: Optional[str] = None
    rank: Optional[str] = None
    current_projects: Optional[list] = []
    mentor: Optional[str] = None
    total_projects: Optional[list] = []
    completed_project: Optional[list] = []

class UserData(BaseModel):
    id: int
    user_role: str
    full_name: str
    email: str
    child: Optional[Union[str, dict]] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    profile_photo: Optional[str] = None
    about_me: Optional[str] = None
    total_students: Optional[int] = 0
    total_sessions: Optional[int] = 0
    rating: Optional[float] = 0.0
    exp: Optional[str] = None
    expertise: Optional[list] = []
    certificate: Optional[list] = []
    active_projects: Optional[int] = 0
    completed_projects: Optional[int] = 0
    achievements: Optional[list] = []
    age: Optional[int] = None
    school: Optional[str] = None
    dob: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_contact: Optional[str] = None
    cgpa: Optional[str] = None
    rank: Optional[str] = None
    current_projects: Optional[list] = []
    mentor: Optional[str] = None
    total_projects: Optional[list] = []
    completed_project: Optional[list] = []
    created_at: Optional[datetime] = None
    is_active: Optional[bool] = True
    
    class Config:
        from_attributes = True
    
class UserResponse(BaseModel):
    status: bool
    message: str
    token: str
    user: dict

class AllUsersResponse(BaseModel):
    success: bool
    message: str
    data: list[UserData]

class UpdateUserModel(BaseModel):
    child: Optional[Union[str, dict]] = None
    user_role: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    profile_photo: Optional[str] = None
    about_me: Optional[str] = None
    total_students: Optional[int] = None
    total_sessions: Optional[int] = None
    rating: Optional[float] = None
    exp: Optional[str] = None
    expertise: Optional[list] = None
    certificate: Optional[list] = None
    active_projects: Optional[int] = None
    completed_projects: Optional[int] = None
    achievements: Optional[list] = None
    age: Optional[int] = None
    school: Optional[str] = None
    dob: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_contact: Optional[str] = None
    cgpa: Optional[str] = None
    rank: Optional[str] = None
    current_projects: Optional[list] = None
    mentor: Optional[str] = None
    total_projects: Optional[list] = None
    completed_project: Optional[list] = None