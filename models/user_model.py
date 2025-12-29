from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserData(BaseModel):
    id: int
    name: str
    email: str

class LoginResponse(BaseModel):
    status: bool
    message: str
    token: str
    admin: UserData

class RegisterResponse(BaseModel):
    status: bool
    message: str
    token: str
    admin: UserData

class UserInDB(BaseModel):
    id: int
    email: str
    name: str
    hashed_password: str
    created_at: datetime
    is_active: bool = True

class TokenData(BaseModel):
    email: Optional[str] = None
