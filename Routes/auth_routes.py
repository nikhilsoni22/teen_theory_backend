from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from models.user_model import UserCreate, UserLogin, RegisterResponse, LoginResponse, UserData
from db.database import get_admin_collection
from utils.auth import get_password_hash, verify_password, create_access_token
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

def get_next_user_id():
    """Get the next available user ID"""
    user_collection = get_admin_collection()
    last_user = user_collection.find_one(sort=[("id", -1)])
    return (last_user["id"] + 1) if last_user else 1

def generate_token():
    """Generate a Laravel-style token"""
    token_id = secrets.randbelow(100)
    random_part = secrets.token_hex(32)
    return f"{token_id}|{random_part}"

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    user_collection = get_admin_collection()
    
    # Check if user already exists
    existing_user = user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Get next user ID
    user_id = get_next_user_id()
    
    # Generate token
    token = generate_token()
    
    # Create new user
    user_dict = {
        "id": user_id,
        "email": user.email,
        "name": user.name or "User",
        "hashed_password": get_password_hash(user.password),
        "token": token,  # Store token in database
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    user_collection.insert_one(user_dict)
    
    # Create response
    return RegisterResponse(
        status=True,
        message="Registration successful",
        token=token,
        admin=UserData(
            id=user_id,
            name=user_dict["name"],
            email=user_dict["email"]
        )
    )

@router.post("/login", response_model=LoginResponse)
async def login(credentials: UserLogin):
    user_collection = get_admin_collection()
    
    # Find user by email
    user = user_collection.find_one({"email": credentials.email})
    
    # Debug logging
    print(f"Login attempt for email: {credentials.email}")
    print(f"User found: {user is not None}")
    
    if not user:
        print("User not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please register first."
        )
    
    if not verify_password(credentials.password, user["hashed_password"]):
        print("Password verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password"
        )
    
    # Generate token
    token = generate_token()
    
    # Update user with new token in database
    user_collection.update_one(
        {"email": credentials.email},
        {"$set": {"token": token}}
    )
    
    print(f"Login successful for user: {user['email']}")
    
    # Create response
    return LoginResponse(
        status=True,
        message="Admin login successful",
        token=token,
        admin=UserData(
            id=user["id"],
            name=user["name"],
            email=user["email"]
        )
    )

@router.get("/me", response_model=dict)
async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current admin details using Bearer token"""
    token = credentials.credentials
    user_collection = get_admin_collection()
    
    # Find admin by token
    admin = user_collection.find_one({"token": token})
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Return admin data
    return {
        "success": True,
        "message": "Admin retrieved successfully",
        "data": {
            "id": admin.get("id"),
            "name": admin.get("name"),
            "email": admin.get("email"),
            "created_at": admin.get("created_at"),
            "is_active": admin.get("is_active", True)
        }
    }