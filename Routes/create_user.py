from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.create_user_model import CreateUserModel, UserResponse, AllUsersResponse, UserData, UpdateUserModel
from db.database import get_user_collection, get_project_collection
from utils.auth import get_password_hash, verify_password
from datetime import datetime
from typing import Optional
import secrets
import os
import shutil

user_router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()

def get_next_user_id():
    """Get the next available user ID"""
    user_collection = get_user_collection()
    last_user = user_collection.find_one(sort=[("id", -1)])
    return (last_user["id"] + 1) if last_user else 1

def generate_token():
    """Generate a Laravel-style token"""
    token_id = secrets.randbelow(100)
    random_part = secrets.token_hex(32)
    return f"{token_id}|{random_part}"


def build_user_profile(user_doc, user_collection, expand_child=False):
    """Build a user profile dict from a DB document.
    If expand_child=True and `child` is an email, replace it with that child's profile (one level deep).
    """
    if not user_doc:
        return None

    # Basic profile mapping (same keys used elsewhere)
    profile = {
        "id": user_doc.get("id"),
        "user_role": user_doc.get("user_role"),
        "full_name": user_doc.get("full_name"),
        "email": user_doc.get("email"),
        "phone_number": user_doc.get("phone_number"),
        "location": user_doc.get("location"),
        "profile_photo": user_doc.get("profile_photo"),
        "about_me": user_doc.get("about_me"),
        "total_students": user_doc.get("total_students", 0),
        "total_sessions": user_doc.get("total_sessions", 0),
        "rating": user_doc.get("rating", 0.0),
        "exp": user_doc.get("exp"),
        "expertise": user_doc.get("expertise", []),
        "certificate": user_doc.get("certificate", []),
        "active_projects": user_doc.get("active_projects", 0),
        "completed_projects": user_doc.get("completed_projects", 0),
        "achievements": user_doc.get("achievements", []),
        "age": user_doc.get("age"),
        "school": user_doc.get("school"),
        "dob": user_doc.get("dob"),
        "guardian_name": user_doc.get("guardian_name"),
        "guardian_contact": user_doc.get("guardian_contact"),
        "cgpa": user_doc.get("cgpa"),
        "rank": user_doc.get("rank"),
        "current_projects": user_doc.get("current_projects", []),
        # child will be resolved below
        "mentor": user_doc.get("mentor"),
        "total_projects": user_doc.get("total_projects", []),
        "completed_project": user_doc.get("completed_project", []),
        "created_at": user_doc.get("created_at"),
        "is_active": user_doc.get("is_active", True)
    }

    child_field = user_doc.get("child")
    # If requested, expand child email into child's profile (one level only)
    if expand_child:
        # child stored as email string
        if isinstance(child_field, str) and "@" in child_field:
            child_doc = user_collection.find_one({"email": child_field})
            if child_doc:
                # Build child's profile but do NOT expand their child to avoid deep recursion
                child_profile = build_user_profile(child_doc, user_collection, expand_child=False)
                # attach child's assigned projects
                try:
                    project_collection = get_project_collection()
                    child_profile["assigned_projects"] = get_assigned_projects_for_user(child_doc, project_collection)
                except Exception:
                    child_profile["assigned_projects"] = []
                profile["child"] = child_profile
            else:
                profile["child"] = child_field
        # child stored as a dict (maybe partial profile)
        elif isinstance(child_field, dict):
            # If dict contains an email, try to fetch full profile
            child_email = child_field.get("email")
            if isinstance(child_email, str) and "@" in child_email:
                child_doc = user_collection.find_one({"email": child_email})
                if child_doc:
                    child_profile = build_user_profile(child_doc, user_collection, expand_child=False)
                    try:
                        project_collection = get_project_collection()
                        child_profile["assigned_projects"] = get_assigned_projects_for_user(child_doc, project_collection)
                    except Exception:
                        child_profile["assigned_projects"] = []
                    profile["child"] = child_profile
                else:
                    # if we can't find full doc, attach what we have and try to compute projects from dict
                    try:
                        project_collection = get_project_collection()
                        profile["child"] = dict(child_field)
                        profile["child"]["assigned_projects"] = get_assigned_projects_for_user(child_field, project_collection)
                    except Exception:
                        profile["child"] = child_field
            else:
                # Assume child_field already is a profile-like dict; try to compute assigned projects
                try:
                    project_collection = get_project_collection()
                    profile["child"] = dict(child_field)
                    profile["child"]["assigned_projects"] = get_assigned_projects_for_user(child_field, project_collection)
                except Exception:
                    profile["child"] = child_field
        else:
            profile["child"] = child_field
    else:
        profile["child"] = child_field

    return profile


def get_assigned_projects_for_user(user_doc, project_collection):
    """Return list of projects assigned to the given user document.
    Matching by stringified MongoDB _id (primary) or email.
    """
    assigned_projects = []
    try:
        all_projects = list(project_collection.find())
    except Exception:
        return []

    # The primary identifier used in assigned_student/assigned_mentor arrays is the stringified MongoDB ObjectId
    user_objid_str = None
    if user_doc.get("_id") is not None:
        user_objid_str = str(user_doc.get("_id"))
    
    user_email = user_doc.get("email")

    for project in all_projects:
        assigned_students = project.get("assigned_student", []) or []
        assigned_mentors = project.get("assigned_mentor", []) or []
        is_assigned = False

        # Check students - the "id" field in assigned_student dicts is the MongoDB ObjectId string
        for student in assigned_students:
            if isinstance(student, dict):
                # Match by _id string (most common) or email
                if (user_objid_str and student.get("id") == user_objid_str) or \
                   (user_email and student.get("email") == user_email):
                    is_assigned = True
                    break
            else:
                # student stored as primitive string (ObjectId)
                if user_objid_str and str(student) == user_objid_str:
                    is_assigned = True
                    break

        # Check mentors if not assigned yet
        if not is_assigned:
            for mentor in assigned_mentors:
                if isinstance(mentor, dict):
                    if (user_objid_str and mentor.get("id") == user_objid_str) or \
                       (user_email and mentor.get("email") == user_email):
                        is_assigned = True
                        break
                else:
                    if user_objid_str and str(mentor) == user_objid_str:
                        is_assigned = True
                        break

        if is_assigned:
            # Build project_info similarly to other endpoints
            raw_milestones = project.get("milestones", []) or []
            processed_milestones = []
            for m in raw_milestones:
                if isinstance(m, dict):
                    m_copy = dict(m)
                else:
                    m_copy = {"name": m}
                raw_tasks = m_copy.get("tasks", []) or []
                new_tasks = []
                for t in raw_tasks:
                    if isinstance(t, dict):
                        t_copy = dict(t)
                    else:
                        t_copy = {"title": t}
                    t_copy.setdefault("status", "pending")
                    new_tasks.append(t_copy)
                m_copy["tasks"] = new_tasks
                m_copy.setdefault("status", "pending")
                processed_milestones.append(m_copy)

            raw_tasks = project.get("tasks", []) or []
            processed_tasks = []
            for t in raw_tasks:
                if isinstance(t, dict):
                    t_copy = dict(t)
                else:
                    t_copy = {"title": t}
                t_copy.setdefault("status", "pending")
                processed_tasks.append(t_copy)

            project_info = {
                "project_id": project.get("id"),
                "title": project.get("title"),
                "project_type": project.get("project_type"),
                "project_description": project.get("project_description"),
                "status": project.get("status", "pending"),
                "created_by_email": project.get("created_by_email"),
                "assigned_student": project.get("assigned_student", []),
                "assigned_mentor": project.get("assigned_mentor", []),
                "project_counsellor": project.get("project_counsellor"),
                "milestones": processed_milestones,
                "tasks": processed_tasks,
                "due_date": project.get("due_date"),
                "attached_files": project.get("attached_files"),
                "created_at": project.get("created_at")
            }
            assigned_projects.append(project_info)

    return assigned_projects

# .......................Create User Endpoint..........................

@user_router.post("/create", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: CreateUserModel):
    user_collection = get_user_collection()
    
    # Check if user already exists
    existing_user = user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Get next user ID
    user_id = get_next_user_id()
    
    # Generate token
    token = generate_token()
    
    # Create user document
    user_dict = {
        "id": user_id,
        "user_role": user.user_role,
        "full_name": user.full_name,
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "token": token,  # Store token in database
        "phone_number": user.phone_number,
        "location": user.location,
        "child" : user.child,
        "profile_photo": user.profile_photo,
        "about_me" : user.about_me,
        "total_students": user.total_students,
        "total_sessions": user.total_sessions,
        "rating": user.rating,
        "exp" : user.exp,
        "expertise": user.expertise,
        "certificate": user.certificate,
        "active_projects": user.active_projects,
        "completed_projects": user.completed_projects,
        "achievements": user.achievements,
        "age": user.age,
        "school" : user.school,
        "dob" : user.dob,
        "guardian_name" : user.guardian_name,
        "guardian_contact" : user.guardian_contact,
        "cgpa" : user.cgpa,
        "rank" : user.rank,
        "current_projects" : user.current_projects,
        "mentor" : user.mentor,
        "total_projects" : user.total_projects,
        "completed_project" : user.completed_project,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    # Insert into database
    result = user_collection.insert_one(user_dict)
    
    # Prepare response (remove hashed_password and _id from response)
    user_dict.pop("hashed_password")
    user_dict["_id"] = str(result.inserted_id)
    
    return {
        "status": True,
        "message": "User created successfully",
        "token": token,
        "user": user_dict
    }
    
    # ........................Get All Users Endpoint..........................

@user_router.get("/all_users", response_model=AllUsersResponse)
async def get_all_users():
    user_collection = get_user_collection()
    users = list(user_collection.find())
    
    # Convert users to UserData format (without password)
    user_data_list = []
    for user in users:
        # Build user profile and expand child (if child contains an email)
        user_profile = build_user_profile(user, user_collection, expand_child=True)
        user_data_list.append(UserData(**user_profile))
    
    return {
        "success": True,
        "message": "Users retrieved successfully",
        "data": user_data_list
    }

# ........................Get Current User Endpoint.........................."

@user_router.get("/me", response_model=dict)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user details using Bearer token"""
    token = credentials.credentials
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Find user by token
    user = user_collection.find_one({"token": token})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get user's _id as string for matching
    user_object_id = str(user.get("_id"))
    
    # Find all projects where this user is assigned (as student or mentor)
    assigned_projects = []
    all_projects = list(project_collection.find())
    
    for project in all_projects:
        assigned_students = project.get("assigned_student", [])
        assigned_mentors = project.get("assigned_mentor", [])
        
        is_assigned = False
        
        # Check if user is in assigned_student list
        for student in assigned_students:
            if isinstance(student, dict) and student.get("id") == user_object_id:
                is_assigned = True
                break
        
        # Check if user is in assigned_mentor list
        if not is_assigned:
            for mentor in assigned_mentors:
                if isinstance(mentor, dict) and mentor.get("id") == user_object_id:
                    is_assigned = True
                    break
        
        if is_assigned:
            # Build project details and ensure milestones/tasks have a 'status' field (default 'pending')
            raw_milestones = project.get("milestones", []) or []
            processed_milestones = []
            for m in raw_milestones:
                if isinstance(m, dict):
                    m_copy = dict(m)
                else:
                    m_copy = {"name": m}
                # Ensure tasks inside milestone have status
                raw_tasks = m_copy.get("tasks", []) or []
                new_tasks = []
                for t in raw_tasks:
                    if isinstance(t, dict):
                        t_copy = dict(t)
                    else:
                        t_copy = {"title": t}
                    t_copy.setdefault("status", "pending")
                    new_tasks.append(t_copy)
                m_copy["tasks"] = new_tasks
                m_copy.setdefault("status", "pending")
                processed_milestones.append(m_copy)

            # Ensure top-level project tasks have status
            raw_tasks = project.get("tasks", []) or []
            processed_tasks = []
            for t in raw_tasks:
                if isinstance(t, dict):
                    t_copy = dict(t)
                else:
                    t_copy = {"title": t}
                t_copy.setdefault("status", "pending")
                processed_tasks.append(t_copy)

            # Get creator user info from created_by_email
            created_by_email = project.get("created_by_email")
            created_by_user = None
            if created_by_email:
                creator = user_collection.find_one({"email": created_by_email})
                if creator:
                    created_by_user = {
                        "_id": str(creator.get("_id")),
                        "id": creator.get("id"),
                        "full_name": creator.get("full_name"),
                        "email": creator.get("email"),
                        "profile_photo": creator.get("profile_photo"),
                        "user_role": creator.get("user_role")
                    }
            
            project_info = {
                "project_id": project.get("id"),
                "title": project.get("title"),
                "project_type": project.get("project_type"),
                "project_description": project.get("project_description"),
                "status": project.get("status", "pending"),
                "created_by_email": created_by_email,
                "created_by_user": created_by_user,
                "assigned_student": project.get("assigned_student", []),
                "assigned_mentor": project.get("assigned_mentor", []),
                "project_counsellor": project.get("project_counsellor"),
                "milestones": processed_milestones,
                "tasks": processed_tasks,
                "due_date": project.get("due_date"),
                "attached_files": project.get("attached_files"),
                "created_at": project.get("created_at")
            }
            assigned_projects.append(project_info)
    
    # Build user profile including expanded child profile
    user_dict = build_user_profile(user, user_collection, expand_child=True)
    # attach assigned projects
    user_dict["assigned_projects"] = assigned_projects
    
    return {
        "success": True,
        "message": "User retrieved successfully",
        "data": user_dict
    }
    
# ALL STUDENT API ENDPOINT.........................
@user_router.get("/all_students")
async def allStudents():
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Filter only users having user_role = "Student"
    students = list(user_collection.find({"user_role": "Student"}))
    
    if not students:
        return {
            "success": True,
            "message": "No students found",
            "data": []
        }
    
    # Add assigned projects to each student and expand child profile
    for student in students:
        student_object_id = str(student.get("_id"))
        student["_id"] = student_object_id

        # Expand child email (if present) into child's profile
        child_field = student.get("child")
        if isinstance(child_field, str) and "@" in child_field:
            child_doc = user_collection.find_one({"email": child_field})
            if child_doc:
                student["child"] = build_user_profile(child_doc, user_collection, expand_child=False)
        
        # Find all projects where this student is assigned
        assigned_projects = []
        all_projects = list(project_collection.find())
        
        for project in all_projects:
            assigned_students = project.get("assigned_student", [])
            
            # Check if student is in assigned_student list
            for assigned_student in assigned_students:
                if isinstance(assigned_student, dict) and assigned_student.get("id") == student_object_id:
                    # Build project details and ensure milestones/tasks have a 'status' field (default 'pending')
                    raw_milestones = project.get("milestones", []) or []
                    processed_milestones = []
                    for m in raw_milestones:
                        if isinstance(m, dict):
                            m_copy = dict(m)
                        else:
                            m_copy = {"name": m}
                        # Ensure tasks inside milestone have status
                        raw_tasks = m_copy.get("tasks", []) or []
                        new_tasks = []
                        for t in raw_tasks:
                            if isinstance(t, dict):
                                t_copy = dict(t)
                            else:
                                t_copy = {"title": t}
                            t_copy.setdefault("status", "pending")
                            new_tasks.append(t_copy)
                        m_copy["tasks"] = new_tasks
                        m_copy.setdefault("status", "pending")
                        processed_milestones.append(m_copy)

                    # Ensure top-level project tasks have status
                    raw_tasks = project.get("tasks", []) or []
                    processed_tasks = []
                    for t in raw_tasks:
                        if isinstance(t, dict):
                            t_copy = dict(t)
                        else:
                            t_copy = {"title": t}
                        t_copy.setdefault("status", "pending")
                        processed_tasks.append(t_copy)

                    project_info = {
                        "project_id": project.get("id"),
                        "title": project.get("title"),
                        "project_type": project.get("project_type"),
                        "project_description": project.get("project_description"),
                        "status": project.get("status", "pending"),
                        "created_by_email": project.get("created_by_email"),
                        "assigned_mentor": project.get("assigned_mentor", []),
                        "project_counsellor": project.get("project_counsellor"),
                        "milestones": processed_milestones,
                        "tasks": processed_tasks,
                        "due_date": project.get("due_date"),
                        "attached_files": project.get("attached_files"),
                        "created_at": project.get("created_at")
                    }
                    assigned_projects.append(project_info)
                    break
        
        # Add assigned_projects to student data
        student["assigned_projects"] = assigned_projects
    
    return {
        "success": True,
        "message": "All students retrieved successfully",
        "data": students
    }
    
    # //......................ALL MENTOR API.............................//
    
@user_router.get("/all_mentors")
async def allMentors():
    user_collection = get_user_collection()
    
    # Filter only users having user_role = "Mentor"
    mentors = list(user_collection.find({"user_role": "Mentor"}))
    
    if not mentors:
        return {
            "success": True,
            "message": "No mentors found",
            "data": []
        }
    
    # Convert ObjectId to string
    for mentor in mentors:
        mentor["_id"] = str(mentor["_id"])
    
    return {
        "success": True,
        "message": "All mentors retrieved successfully",
        "data": mentors
    }

@user_router.get("/all_counsellors")
async def allCounsellors():
    user_collection = get_user_collection()

    # Filter only users having user_role = "Counsellor"
    counsellors = list(user_collection.find({"user_role": "Counsellor"}))

    if not counsellors:
        return {
            "success": True,
            "message": "No counsellors found",
            "data": []
        }

    # Convert ObjectId to string for each counsellor
    for c in counsellors:
        c["_id"] = str(c["_id"])

    return {
        "success": True,
        "message": "All counsellors retrieved successfully",
        "data": counsellors
    }


@user_router.get("/{user_id}", response_model=dict)
async def get_user_by_id(user_id: int):
    """Get user details by user ID"""
    user_collection = get_user_collection()
    
    # Find user by ID
    user = user_collection.find_one({"id": user_id})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Build user profile and expand child profile
    user_dict = build_user_profile(user, user_collection, expand_child=True)
    
    return {
        "success": True,
        "message": "User retrieved successfully",
        "data": user_dict
    }
    
# ........................Update User Endpoint..........................

@user_router.put("/update")
async def update_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_role: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    profile_photo: Optional[UploadFile] = File(None),
    about_me: Optional[str] = Form(None),
    total_students: Optional[int] = Form(None),
    total_sessions: Optional[int] = Form(None),
    rating: Optional[float] = Form(None),
    exp: Optional[str] = Form(None),
    expertise: Optional[str] = Form(None),  # JSON string
    certificate: Optional[str] = Form(None),  # JSON string
    active_projects: Optional[int] = Form(None),
    completed_projects: Optional[int] = Form(None),
    achievements: Optional[str] = Form(None),  # JSON string
    age: Optional[int] = Form(None),
    school: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    guardian_name: Optional[str] = Form(None),
    guardian_contact: Optional[str] = Form(None),
    cgpa: Optional[str] = Form(None),
    rank: Optional[str] = Form(None),
    current_projects: Optional[str] = Form(None),  # JSON string
    mentor: Optional[str] = Form(None),
    total_projects: Optional[str] = Form(None),  # JSON string
    completed_project: Optional[str] = Form(None)  # JSON string
):
    """Update user details using Bearer token with file upload support"""
    import json
    
    token = credentials.credentials
    user_collection = get_user_collection()
    
    # Find user by token
    user = user_collection.find_one({"token": token})
    
    if not user:
        return {
            "success": False,
            "message": "Invalid or expired token"
        }
    
    # Prepare update data
    update_data = {}
    
    if user_role is not None:
        update_data["user_role"] = user_role
    if full_name is not None:
        update_data["full_name"] = full_name
    if phone_number is not None:
        update_data["phone_number"] = phone_number
    if location is not None:
        update_data["location"] = location
    
    # Handle profile photo upload
    if profile_photo is not None:
        # Create uploads directory if not exists
        upload_dir = "uploads/profile_photos"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(profile_photo.filename)[1]
        unique_filename = f"user_{user['id']}_{secrets.token_hex(8)}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        
        # Store relative path in database
        update_data["profile_photo"] = f"/{file_path.replace(os.sep, '/')}"
    
    if about_me is not None:
        update_data["about_me"] = about_me
    if total_students is not None:
        update_data["total_students"] = total_students
    if total_sessions is not None:
        update_data["total_sessions"] = total_sessions
    if rating is not None:
        update_data["rating"] = rating
    if exp is not None:
        update_data["exp"] = exp
    
    # Parse JSON strings for list fields
    if expertise is not None and expertise.strip():
        try:
            update_data["expertise"] = json.loads(expertise)
        except:
            update_data["expertise"] = [expertise]
    
    if certificate is not None and certificate.strip():
        try:
            update_data["certificate"] = json.loads(certificate)
        except:
            update_data["certificate"] = [certificate]
    
    if active_projects is not None:
        update_data["active_projects"] = active_projects
    if completed_projects is not None:
        update_data["completed_projects"] = completed_projects
    
    if achievements is not None and achievements.strip():
        try:
            update_data["achievements"] = json.loads(achievements)
        except:
            update_data["achievements"] = [achievements]
    
    if age is not None:
        update_data["age"] = age
    if school is not None:
        update_data["school"] = school
    if dob is not None:
        update_data["dob"] = dob
    if guardian_name is not None:
        update_data["guardian_name"] = guardian_name
    if guardian_contact is not None:
        update_data["guardian_contact"] = guardian_contact
    if cgpa is not None:
        update_data["cgpa"] = cgpa
    if rank is not None:
        update_data["rank"] = rank
    
    if current_projects is not None and current_projects.strip():
        try:
            update_data["current_projects"] = json.loads(current_projects)
        except:
            update_data["current_projects"] = [current_projects]
    
    if mentor is not None:
        update_data["mentor"] = mentor
    
    if total_projects is not None and total_projects.strip():
        try:
            update_data["total_projects"] = json.loads(total_projects)
        except:
            update_data["total_projects"] = [total_projects]
    
    if completed_project is not None and completed_project.strip():
        try:
            update_data["completed_project"] = json.loads(completed_project)
        except:
            update_data["completed_project"] = [completed_project]
    
    if not update_data:
        return {
            "success": False,
            "message": "No fields to update"
        }
    
    # Add updated timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update user in database
    user_collection.update_one(
        {"_id": user["_id"]},
        {"$set": update_data}
    )
    
    # Get updated user
    updated_user = user_collection.find_one({"_id": user["_id"]})
    
    # Convert to response format (without password)
    user_dict = {
        "id": updated_user.get("id"),
        "user_role": updated_user.get("user_role"),
        "full_name": updated_user.get("full_name"),
        "email": updated_user.get("email"),
        "phone_number": updated_user.get("phone_number"),
        "location": updated_user.get("location"),
        "profile_photo": updated_user.get("profile_photo"),
        "about_me": updated_user.get("about_me"),
        "total_students": updated_user.get("total_students", 0),
        "total_sessions": updated_user.get("total_sessions", 0),
        "rating": updated_user.get("rating", 0.0),
        "exp": updated_user.get("exp"),
        "expertise": updated_user.get("expertise", []),
        "certificate": updated_user.get("certificate", []),
        "active_projects": updated_user.get("active_projects", 0),
        "completed_projects": updated_user.get("completed_projects", 0),
        "achievements": updated_user.get("achievements", []),
        "age": updated_user.get("age"),
        "school": updated_user.get("school"),
        "dob": updated_user.get("dob"),
        "guardian_name": updated_user.get("guardian_name"),
        "guardian_contact": updated_user.get("guardian_contact"),
        "cgpa": updated_user.get("cgpa"),
        "rank": updated_user.get("rank"),
        "current_projects": updated_user.get("current_projects", []),
        "mentor": updated_user.get("mentor"),
        "total_projects": updated_user.get("total_projects", []),
        "completed_project": updated_user.get("completed_project", []),
        "created_at": updated_user.get("created_at"),
        "updated_at": updated_user.get("updated_at"),
        "is_active": updated_user.get("is_active", True)
    }
    
    return {
        "success": True,
        "message": "User updated successfully",
        "data": user_dict
    }
    
# ........................User Login Endpoint..........................
    
@user_router.post("/user_login", response_model=dict)
async def user_login(payload: dict):
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required"
        )

    user_collection = get_user_collection()
    user = user_collection.find_one({"email": email})
    if not user:
        return {
            "success" : False,
            "message" : "User not found. Please register first."
        }
        
    if not verify_password(password, user.get("hashed_password", "")):
        return {
            "success" : False,
            "message" : "Incorrect password"
        }

    # Generate a new token and store it
    token = generate_token()
    user_collection.update_one({"_id": user["_id"]}, {"$set": {"token": token}})

    # Prepare response without sensitive fields
    user["token"] = token
    user.pop("hashed_password", None)
    user["_id"] = str(user["_id"])

    return {
        "success": True,
        "message": "Login successful",
        "token": token,
        "user": user
    }
    
    
    