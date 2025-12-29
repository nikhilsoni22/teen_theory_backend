from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Form, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.project_model import ProjectModel, ProjectResponse
from db.database import get_project_collection, get_user_collection
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
import secrets
import os
import shutil
import json

project_router = APIRouter(prefix="/projects", tags=["Projects"])
security = HTTPBearer()

def get_next_project_id():
    """Get the next available project ID"""
    project_collection = get_project_collection()
    last_project = project_collection.find_one(sort=[("id", -1)])
    return (last_project["id"] + 1) if last_project else 1



# CREATE PEOJECT ENDPOINTs...........................
@project_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_project(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    title: str = Form(...),
    project_type: str = Form(...),
    project_description: str = Form(...),
    status_field: str = Form("pending"),
    assigned_student: Optional[str] = Form(None),
    assigned_mentor: Optional[str] = Form(None),
    project_counsellor: Optional[str] = Form(None),
    milestones: Optional[str] = Form(None),
    tasks: Optional[str] = Form(None),
    deliverables_title: Optional[str] = Form(None),
    deliverables_type: Optional[List[str]] = Form(None),
    due_date: Optional[str] = Form(None),
    linked_milestones: Optional[str] = Form(None),
    metadata_and_req: Optional[str] = Form(None),
    page_limit: Optional[str] = Form(None),
    additional_instructions: Optional[str] = Form(None),
    allow_multiple_submissions: Optional[bool] = Form(False),
    montor_approval: Optional[bool] = Form(False),
    counsellor_approval: Optional[bool] = Form(False),
    resources_type: Optional[str] = Form(None),
    resources_title: Optional[str] = Form(None),
    resources_description: Optional[str] = Form(None),
    attached_files: Optional[UploadFile] = File(None),
    student_visibility: Optional[bool] = Form(True),
    mentor_visibility: Optional[bool] = Form(True),
    session_type: Optional[str] = Form(None),
    purpose: Optional[str] = Form(None),
    preferred_time: Optional[str] = Form(None),
    duration: Optional[str] = Form(None)
):
    """Create a new project with file upload support"""
    token = credentials.credentials
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        return {
            "success": False,
            "message": "Invalid or expired token"
        }
    
    # Get next project ID
    project_id = get_next_project_id()
    
    # Handle file upload if provided
    file_path = None
    if attached_files is not None:
        # Create uploads directory
        upload_dir = "uploads/project_files"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(attached_files.filename)[1]
        unique_filename = f"project_{project_id}_{secrets.token_hex(8)}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(attached_files.file, buffer)
        
        # Store relative path
        file_path = f"/{file_path.replace(os.sep, '/')}"
    
    # Parse JSON arrays
    assigned_student_list = []
    if assigned_student and assigned_student.strip():
        try:
            assigned_student_list = json.loads(assigned_student)
        except:
            assigned_student_list = [assigned_student]
    
    assigned_mentor_list = []
    if assigned_mentor and assigned_mentor.strip():
        try:
            assigned_mentor_list = json.loads(assigned_mentor)
        except:
            assigned_mentor_list = [assigned_mentor]
    
    milestones_list = []
    if milestones and milestones.strip():
        try:
            milestones_list = json.loads(milestones)
        except:
            milestones_list = [milestones]

    # Normalize milestones: ensure each milestone is a dict with a unique 'id', default status, and tasks with statuses
    normalized_milestones = []
    for idx, m in enumerate(milestones_list):
        if isinstance(m, dict):
            m_copy = dict(m)
        else:
            # if milestone provided as primitive, convert to dict with name
            m_copy = {"name": m}

        # assign an id if missing
        if not m_copy.get("id"):
            m_copy["id"] = f"{project_id}-{idx}-{secrets.token_hex(6)}"

        # ensure status
        m_copy.setdefault("status", "pending")

        # normalize tasks inside milestone
        raw_tasks = m_copy.get("tasks", []) or []
        normalized_tasks = []
        for t in raw_tasks:
            if isinstance(t, dict):
                t_copy = dict(t)
            else:
                t_copy = {"title": t}
            t_copy.setdefault("status", "pending")
            normalized_tasks.append(t_copy)
        m_copy["tasks"] = normalized_tasks

        normalized_milestones.append(m_copy)
    # use normalized_milestones in the project document
    milestones_list = normalized_milestones
    
    tasks_list = []
    if tasks and tasks.strip():
        try:
            tasks_list = json.loads(tasks)
        except:
            tasks_list = [tasks]

    # Normalize deliverables_type into a list. Accepts:
    # - multiple form fields (List[str])
    # - JSON array string
    # - comma-separated string
    deliverables_type_list: List[str] = []
    if deliverables_type:
        # If FastAPI provided a list already
        if isinstance(deliverables_type, list):
            # filter out empty strings and strip whitespace
            deliverables_type_list = [str(x).strip() for x in deliverables_type if x and str(x).strip()]
        else:
            # try parsing JSON
            try:
                parsed = json.loads(deliverables_type)
                if isinstance(parsed, list):
                    deliverables_type_list = [str(x).strip() for x in parsed if x and str(x).strip()]
                else:
                    # fallback to single value
                    deliverables_type_list = [str(parsed).strip()]
            except Exception:
                # comma-separated or single string
                s = str(deliverables_type)
                if "," in s:
                    deliverables_type_list = [p.strip() for p in s.split(",") if p.strip()]
                elif s.strip():
                    deliverables_type_list = [s.strip()]
    
    # Create project document
    project_dict = {
        "id": project_id,
        "title": title,
        "project_type": project_type,
        "project_description": project_description,
        "status": status_field,
        "created_by_email": user.get("email"),
        "assigned_student": assigned_student_list,
        "assigned_mentor": assigned_mentor_list,
        "project_counsellor": project_counsellor,
        "milestones": milestones_list,
        "tasks": tasks_list,
        "deliverables_title": deliverables_title,
        "deliverables_type": deliverables_type,
        "due_date": due_date,
        "linked_milestones": linked_milestones,
        "metadata_and_req": metadata_and_req,
        "page_limit": page_limit,
        "additional_instructions": additional_instructions,
        "allow_multiple_submissions": allow_multiple_submissions,
        "montor_approval": montor_approval,
        "counsellor_approval": counsellor_approval,
        "resources_type": resources_type,
        "resources_title": resources_title,
        "resources_description": resources_description,
        "attached_files": file_path,
        "student_visibility": student_visibility,
        "mentor_visibility": mentor_visibility,
        "session_type": session_type,
        "purpose": purpose,
        "preferred_time": preferred_time,
        "duration": duration,
        "created_at": datetime.utcnow()
    }
    
    # Insert into database
    result = project_collection.insert_one(project_dict)
    project_dict["_id"] = str(result.inserted_id)
    
    # Update assigned students' current_projects field
    if assigned_student_list:
        for student_data in assigned_student_list:
            # Extract student ID from the assigned_student object
            if isinstance(student_data, dict):
                student_id = student_data.get("id")
            else:
                student_id = student_data
            
            if student_id:
                try:
                    # Find student by _id (MongoDB ObjectId)
                    student = user_collection.find_one({"_id": ObjectId(student_id)})
                    
                    if student:
                        # Get current projects list
                        current_projects = student.get("current_projects", [])
                        
                        # Add new project info
                        project_info = {
                            "project_id": project_id,
                            "title": title,
                            "status": status_field,
                            "assigned_date": datetime.utcnow()
                        }
                        
                        # Append to current_projects
                        current_projects.append(project_info)
                        
                        # Update student's current_projects
                        user_collection.update_one(
                            {"_id": ObjectId(student_id)},
                            {"$set": {"current_projects": current_projects}}
                        )
                except Exception as e:
                    # Log error but don't fail project creation
                    print(f"Error updating student {student_id}: {e}")
    
    # Update assigned mentors' assigned_projects field
    if assigned_mentor_list:
        for mentor_data in assigned_mentor_list:
            # Extract mentor ID from the assigned_mentor object
            if isinstance(mentor_data, dict):
                mentor_id = mentor_data.get("id")
            else:
                mentor_id = mentor_data
            
            if mentor_id:
                try:
                    # Find mentor by _id (MongoDB ObjectId)
                    mentor = user_collection.find_one({"_id": ObjectId(mentor_id)})
                    
                    if mentor:
                        # Get assigned projects list
                        assigned_projects = mentor.get("assigned_projects", [])
                        
                        # Add new project info
                        project_info = {
                            "project_id": project_id,
                            "title": title,
                            "status": status_field,
                            "assigned_date": datetime.utcnow()
                        }
                        
                        # Append to assigned_projects
                        assigned_projects.append(project_info)
                        
                        # Update mentor's assigned_projects
                        user_collection.update_one(
                            {"_id": ObjectId(mentor_id)},
                            {"$set": {"assigned_projects": assigned_projects}}
                        )
                except Exception as e:
                    # Log error but don't fail project creation
                    print(f"Error updating mentor {mentor_id}: {e}")
    
    return {
        "success": True,
        "message": "Project created successfully",
        "data": project_dict
    }

# ........................Get All Projects Endpoint..........................

@project_router.get("/all_projects")
async def get_all_projects():
    """Get all projects"""
    project_collection = get_project_collection()
    projects = list(project_collection.find())
    
    # Convert projects to response format
    project_list = []
    for project in projects:
        # Ensure milestones and tasks include a status (default 'pending') and project status defaults to 'pending'
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

        project_dict = {
            "id": project.get("id"),
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
            "deliverables_title": project.get("deliverables_title"),
            "deliverables_type": project.get("deliverables_type"),
            "due_date": project.get("due_date"),
            "linked_milestones": project.get("linked_milestones"),
            "metadata_and_req": project.get("metadata_and_req"),
            "page_limit": project.get("page_limit"),
            "additional_instructions": project.get("additional_instructions"),
            "allow_multiple_submissions": project.get("allow_multiple_submissions", False),
            "montor_approval": project.get("montor_approval", False),
            "counsellor_approval": project.get("counsellor_approval", False),
            "resources_type": project.get("resources_type"),
            "resources_title": project.get("resources_title"),
            "resources_description": project.get("resources_description"),
            "attached_files": project.get("attached_files"),
            "student_visibility": project.get("student_visibility", True),
            "mentor_visibility": project.get("mentor_visibility", True),
            "session_type": project.get("session_type"),
            "purpose": project.get("purpose"),
            "preferred_time": project.get("preferred_time"),
            "duration": project.get("duration"),
            "created_at": project.get("created_at")
        }
        project_list.append(project_dict)
    
    return {
        "success": True,
        "message": "Projects retrieved successfully",
        "data": project_list
    }


@project_router.get('/by_mentor')
async def get_projects_by_mentor(email: str = None):
    """Return projects where any assigned_mentor entry has the given email.

    Query param: `email` (required)
    """
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`email` query parameter is required")

    project_collection = get_project_collection()
    try:
        # match mentor entries that are dicts with an email field
        projects = list(project_collection.find({"assigned_mentor.email": email}))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch projects: {e}")

    project_list = []
    for project in projects:
        # Ensure milestones and tasks include a status (default 'pending') and project status defaults to 'pending'
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

        project_dict = {
            "id": project.get("id"),
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
            "deliverables_title": project.get("deliverables_title"),
            "deliverables_type": project.get("deliverables_type"),
            "due_date": project.get("due_date"),
            "linked_milestones": project.get("linked_milestones"),
            "metadata_and_req": project.get("metadata_and_req"),
            "page_limit": project.get("page_limit"),
            "additional_instructions": project.get("additional_instructions"),
            "allow_multiple_submissions": project.get("allow_multiple_submissions", False),
            "montor_approval": project.get("montor_approval", False),
            "counsellor_approval": project.get("counsellor_approval", False),
            "resources_type": project.get("resources_type"),
            "resources_title": project.get("resources_title"),
            "resources_description": project.get("resources_description"),
            "attached_files": project.get("attached_files"),
            "student_visibility": project.get("student_visibility", True),
            "mentor_visibility": project.get("mentor_visibility", True),
            "session_type": project.get("session_type"),
            "purpose": project.get("purpose"),
            "preferred_time": project.get("preferred_time"),
            "duration": project.get("duration"),
            "created_at": project.get("created_at")
        }
        project_list.append(project_dict)

    return {"success": True, "message": f"Projects for mentor {email} retrieved successfully", "data": project_list}

# ........................Get Projects By Creator Email..........................

@project_router.get("/my_projects")
async def get_my_projects(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get all projects created by current user using Bearer token"""
    token = credentials.credentials
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        return {
            "success": False,
            "message": "Invalid or expired token"
        }
    
    # Get projects created by this user
    creator_email = user.get("email")
    projects = list(project_collection.find({"created_by_email": creator_email}))
    
    # Convert projects to response format
    project_list = []
    for project in projects:
        # Ensure milestones and tasks include a status (default 'pending') and project status defaults to 'pending'
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

        project_dict = {
            "id": project.get("id"),
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
            "deliverables_title": project.get("deliverables_title"),
            "deliverables_type": project.get("deliverables_type"),
            "due_date": project.get("due_date"),
            "linked_milestones": project.get("linked_milestones"),
            "metadata_and_req": project.get("metadata_and_req"),
            "page_limit": project.get("page_limit"),
            "additional_instructions": project.get("additional_instructions"),
            "allow_multiple_submissions": project.get("allow_multiple_submissions", False),
            "montor_approval": project.get("montor_approval", False),
            "counsellor_approval": project.get("counsellor_approval", False),
            "resources_type": project.get("resources_type"),
            "resources_title": project.get("resources_title"),
            "resources_description": project.get("resources_description"),
            "attached_files": project.get("attached_files"),
            "student_visibility": project.get("student_visibility", True),
            "mentor_visibility": project.get("mentor_visibility", True),
            "session_type": project.get("session_type"),
            "purpose": project.get("purpose"),
            "preferred_time": project.get("preferred_time"),
            "duration": project.get("duration"),
            "created_at": project.get("created_at")
        }
        project_list.append(project_dict)
    
    return {
        "success": True,
        "message": f"Projects created by {creator_email} retrieved successfully",
        "data": project_list
    }


@project_router.get("/notifications/by_student")
async def get_project_notifications_for_student(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return project notifications (title + created_at) for the authenticated student."""

    token = credentials.credentials
    project_collection = get_project_collection()
    user_collection = get_user_collection()

    target_user = user_collection.find_one({"token": token})
    if not target_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    email = target_user.get("email")
    target_user_id = str(target_user.get("_id")) if target_user else None

    notifications = []
    projects = list(project_collection.find())

    for project in projects:
        assigned_students = project.get("assigned_student", []) or []
        match_found = False
        for assigned in assigned_students:
            # Allow dicts with email/id or direct strings (email/id)
            if isinstance(assigned, dict):
                assigned_email = assigned.get("email")
                assigned_id = str(assigned.get("id")) if assigned.get("id") else None
                if assigned_email and email and assigned_email.lower() == email.lower():
                    match_found = True
                    break
                if target_user_id and assigned_id and assigned_id == target_user_id:
                    match_found = True
                    break
            else:
                value = str(assigned)
                if target_user_id and value == target_user_id:
                    match_found = True
                    break
                if email and value.lower() == email.lower():
                    match_found = True
                    break

        if match_found:
            assigned_by_email = project.get("created_by_email")
            assigned_by_user = None
            if assigned_by_email:
                try:
                    creator = user_collection.find_one({"email": assigned_by_email})
                    if creator:
                        assigned_by_user = {
                            "_id": str(creator.get("_id")),
                            "id": creator.get("id"),
                            "full_name": creator.get("full_name"),
                            "email": creator.get("email"),
                            "profile_photo": creator.get("profile_photo"),
                            "user_role": creator.get("user_role"),
                        }
                except Exception:
                    assigned_by_user = None

            notifications.append({
                "project_id": project.get("id"),
                "title": project.get("title"),
                "status": project.get("status", "pending"),
                "created_at": project.get("created_at"),
                "assigned_by": assigned_by_email,
                "assigned_by_user": assigned_by_user
            })

    return {
        "success": True,
        "message": f"Notifications for {email} retrieved successfully",
        "data": notifications
    }


@project_router.put("/status")
async def update_project_status(payload: dict = Body(...)):
    """Update a project's status and propagate the change to related user records."""
    project_id = payload.get("project_id")
    new_status = payload.get("status")

    if project_id is None or not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`project_id` and `status` are required")

    project_collection = get_project_collection()
    user_collection = get_user_collection()

    # Normalize project_id to int when possible
    try:
        if isinstance(project_id, str) and project_id.isdigit():
            normalized_project_id = int(project_id)
        else:
            normalized_project_id = project_id
    except Exception:
        normalized_project_id = project_id

    project = project_collection.find_one({"id": normalized_project_id})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {project_id} not found")

    project_collection.update_one(
        {"id": normalized_project_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )

    # Update students' current_projects status
    assigned_students = project.get("assigned_student", []) or []
    for student in assigned_students:
        student_id = None
        if isinstance(student, dict):
            student_id = student.get("id")
        else:
            student_id = student

        if not student_id:
            continue

        try:
            user = user_collection.find_one({"_id": ObjectId(student_id)})
        except Exception:
            user = None

        if not user:
            continue

        current_projects = user.get("current_projects", [])
        updated = False
        for proj in current_projects:
            if proj.get("project_id") == project.get("id"):
                proj["status"] = new_status
                updated = True
        if updated:
            user_collection.update_one({"_id": user["_id"]}, {"$set": {"current_projects": current_projects}})

    # Update mentors' assigned_projects status
    assigned_mentors = project.get("assigned_mentor", []) or []
    for mentor in assigned_mentors:
        mentor_id = None
        if isinstance(mentor, dict):
            mentor_id = mentor.get("id")
        else:
            mentor_id = mentor

        if not mentor_id:
            continue

        try:
            user = user_collection.find_one({"_id": ObjectId(mentor_id)})
        except Exception:
            user = None

        if not user:
            continue

        assigned_projects = user.get("assigned_projects", [])
        updated = False
        for proj in assigned_projects:
            if proj.get("project_id") == project.get("id"):
                proj["status"] = new_status
                updated = True
        if updated:
            user_collection.update_one({"_id": user["_id"]}, {"$set": {"assigned_projects": assigned_projects}})

    updated_project = project_collection.find_one({"id": normalized_project_id})

    return {
        "success": True,
        "message": "Project status updated successfully",
        "data": {
            "id": updated_project.get("id"),
            "title": updated_project.get("title"),
            "status": new_status,
            "updated_at": updated_project.get("updated_at")
        }
    }


@project_router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a project and remove references from assigned students and mentors."""
    
    token = credentials.credentials
    project_collection = get_project_collection()
    user_collection = get_user_collection()
    
    requesting_user = user_collection.find_one({"token": token})
    if not requesting_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    # Normalize project_id to int when possible
    try:
        if isinstance(project_id, str) and project_id.isdigit():
            normalized_project_id = int(project_id)
        else:
            normalized_project_id = project_id
    except Exception:
        normalized_project_id = project_id
    
    project = project_collection.find_one({"id": normalized_project_id})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {project_id} not found")
    
    creator_email = project.get("created_by_email")
    requester_email = requesting_user.get("email")
    requester_role = (requesting_user.get("user_role") or "").lower()
    
    # Only allow creator, admin, or counsellor to delete
    if creator_email != requester_email and requester_role not in {"admin", "counsellor"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this project")
    
    # Clean up students' current_projects
    assigned_students = project.get("assigned_student", []) or []
    for student in assigned_students:
        student_id = student.get("id") if isinstance(student, dict) else student
        if not student_id:
            continue
        try:
            user = user_collection.find_one({"_id": ObjectId(student_id)})
        except Exception:
            user = None
        if not user:
            continue
        current_projects = user.get("current_projects", [])
        filtered = [proj for proj in current_projects if proj.get("project_id") != project.get("id")]
        if len(filtered) != len(current_projects):
            user_collection.update_one({"_id": user["_id"]}, {"$set": {"current_projects": filtered}})
    
    # Clean up mentors' assigned_projects
    assigned_mentors = project.get("assigned_mentor", []) or []
    for mentor in assigned_mentors:
        mentor_id = mentor.get("id") if isinstance(mentor, dict) else mentor
        if not mentor_id:
            continue
        try:
            user = user_collection.find_one({"_id": ObjectId(mentor_id)})
        except Exception:
            user = None
        if not user:
            continue
        assigned_projects = user.get("assigned_projects", [])
        filtered = [proj for proj in assigned_projects if proj.get("project_id") != project.get("id")]
        if len(filtered) != len(assigned_projects):
            user_collection.update_one({"_id": user["_id"]}, {"$set": {"assigned_projects": filtered}})
    
    # Remove attached project file if stored locally
    attached_file = project.get("attached_files")
    if attached_file:
        file_path = attached_file.lstrip("/\\")
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
    
    # Delete the project
    project_collection.delete_one({"id": normalized_project_id})
    
    return {
        "success": True,
        "message": f"Project {project_id} deleted successfully"
    }


# UPDATE MILESTONE STATUS ENDPOINT..........................
@project_router.put("/milestone_status")
async def update_milestone_status(
    project_id: str = Form(...),
    status: str = Form(...),
    milestone_id: Optional[str] = Form(None),
    milestone_name: Optional[str] = Form(None),
    task_title: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None)
):
    """Update status of a milestone or a task inside a milestone and optionally attach a file.

    Form fields:
    - project_id (required)
    - status (required)
    - milestone_id (optional) — matches by milestone `id`
    - milestone_name (optional) — fallback match by name
    - task_title (optional) — update only the matching task
    - attachment (optional file) — will be saved and attached to the milestone or task
    """
    project_collection = get_project_collection()

    status_value = status

    if not project_id or not status_value:
        return {"success": False, "message": "`project_id` and `status` are required"}

    # normalize project_id to int when possible
    try:
        if isinstance(project_id, str) and project_id.isdigit():
            project_id_int = int(project_id)
        else:
            project_id_int = project_id
    except Exception:
        project_id_int = project_id

    project = project_collection.find_one({"id": project_id_int})
    if not project:
        return {"success": False, "message": f"Project with id {project_id} not found"}

    milestones = project.get("milestones", []) or []
    modified = False

    # helper to save attachment and return public path
    attachment_path = None
    if attachment is not None:
        upload_dir = "uploads/milestone_attachments"
        os.makedirs(upload_dir, exist_ok=True)
        file_extension = os.path.splitext(attachment.filename or "")[1]
        unique_filename = f"proj_{project_id}_ms_{secrets.token_hex(8)}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)
        attachment_path = f"/{file_path.replace(os.sep, '/')}"

    # If milestone_id provided, match by id; otherwise if milestone_name provided match by name
    if milestone_id:
        for m in milestones:
            m_id = m.get("id") if isinstance(m, dict) else None
            if m_id == milestone_id:
                # update milestone status
                if isinstance(m, dict):
                    m["status"] = status_value
                    # attach file to milestone if provided
                    if attachment_path:
                        m.setdefault("attachments", []).append(attachment_path)
                    # If task_title provided, update only that task
                    if task_title:
                        tasks = m.get("tasks", []) or []
                        for t in tasks:
                            if (isinstance(t, dict) and t.get("title") == task_title) or (not isinstance(t, dict) and t == task_title):
                                if isinstance(t, dict):
                                    t["status"] = status_value
                                    if attachment_path:
                                        t.setdefault("attachments", []).append(attachment_path)
                                else:
                                    idx = tasks.index(t)
                                    tasks[idx] = {"title": t, "status": status_value, "attachments": ([attachment_path] if attachment_path else [])}
                                modified = True
                                break
                    else:
                        # update all tasks under this milestone to given status
                        tasks = m.get("tasks", []) or []
                        for t in tasks:
                            if isinstance(t, dict):
                                t["status"] = status_value
                                if attachment_path:
                                    t.setdefault("attachments", []).append(attachment_path)
                            else:
                                idx = tasks.index(t)
                                tasks[idx] = {"title": t, "status": status_value, "attachments": ([attachment_path] if attachment_path else [])}
                        modified = True
                else:
                    idx = milestones.index(m)
                    new_m = {"name": m, "id": milestone_id, "status": status_value, "tasks": []}
                    if attachment_path:
                        new_m["attachments"] = [attachment_path]
                    milestones[idx] = new_m
                    modified = True
                break
    elif milestone_name:
        for m in milestones:
            # allow matching by name (string) or dict name
            name = m.get("name") if isinstance(m, dict) else None
            if name == milestone_name:
                # update milestone status
                if isinstance(m, dict):
                    m["status"] = status_value
                    if attachment_path:
                        m.setdefault("attachments", []).append(attachment_path)
                    # If task_title provided, update only that task
                    if task_title:
                        tasks = m.get("tasks", []) or []
                        for t in tasks:
                            if (isinstance(t, dict) and t.get("title") == task_title) or (not isinstance(t, dict) and t == task_title):
                                if isinstance(t, dict):
                                    t["status"] = status_value
                                    if attachment_path:
                                        t.setdefault("attachments", []).append(attachment_path)
                                else:
                                    idx = tasks.index(t)
                                    tasks[idx] = {"title": t, "status": status_value, "attachments": ([attachment_path] if attachment_path else [])}
                                modified = True
                                break
                    else:
                        tasks = m.get("tasks", []) or []
                        for t in tasks:
                            if isinstance(t, dict):
                                t["status"] = status_value
                                if attachment_path:
                                    t.setdefault("attachments", []).append(attachment_path)
                            else:
                                idx = tasks.index(t)
                                tasks[idx] = {"title": t, "status": status_value, "attachments": ([attachment_path] if attachment_path else [])}
                        modified = True
                else:
                    idx = milestones.index(m)
                    new_m = {"name": m, "status": status_value, "tasks": []}
                    if attachment_path:
                        new_m["attachments"] = [attachment_path]
                    milestones[idx] = new_m
                    modified = True
                break
    else:
        # No specific milestone -> update all milestones and their tasks
        for i, m in enumerate(milestones):
            if isinstance(m, dict):
                m["status"] = status_value
                if attachment_path:
                    m.setdefault("attachments", []).append(attachment_path)
                tasks = m.get("tasks", []) or []
                for t in tasks:
                    if isinstance(t, dict):
                        t["status"] = status_value
                        if attachment_path:
                            t.setdefault("attachments", []).append(attachment_path)
                    else:
                        idx = tasks.index(t)
                        tasks[idx] = {"title": t, "status": status_value, "attachments": ([attachment_path] if attachment_path else [])}
            else:
                milestones[i] = {"name": m, "status": status_value, "tasks": []}
                if attachment_path:
                    milestones[i]["attachments"] = [attachment_path]
        modified = True

    if not modified:
        # nothing changed (e.g., milestone or task not found)
        return {"success": False, "message": "No matching milestone/task found or nothing to update"}

    # Persist changes (update milestones array)
    project_collection.update_one({"id": project_id_int}, {"$set": {"milestones": milestones, "updated_at": datetime.utcnow()}})

    # Return updated project excerpt
    return {"success": True, "message": "Milestone/task status updated", "data": {"project_id": project_id_int, "milestones": milestones}}


@project_router.put("/milestone/status")
async def update_milestone_status_json(
    payload: dict = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update the status of a specific milestone (e.g., approved, rejected, pending).
    
    Request body:
    {
        "project_id": 1,
        "milestone_id": "milestone-id-here",
        "status": "approved" | "rejected" | "pending" | etc.
    }
    """
    token = credentials.credentials
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    # Requester's email (derived from token)
    requester_email = user.get("email")
    
    # Requester's email (derived from token)
    requester_email = user.get("email")
    
    project_id = payload.get("project_id")
    milestone_id = payload.get("milestone_id")
    new_status = payload.get("status")
    
    if not project_id or not milestone_id or not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="`project_id`, `milestone_id`, and `status` are required"
        )
    
    # Normalize project_id to int when possible
    try:
        if isinstance(project_id, str) and project_id.isdigit():
            normalized_project_id = int(project_id)
        else:
            normalized_project_id = project_id
    except Exception:
        normalized_project_id = project_id
    
    project = project_collection.find_one({"id": normalized_project_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Project with id {project_id} not found"
        )
    
    milestones = project.get("milestones", []) or []
    milestone_found = False
    updated_milestone = None
    
    # Find and update the specific milestone
    for m in milestones:
        if isinstance(m, dict) and m.get("id") == milestone_id:
            m["status"] = new_status
            m["updated_at"] = datetime.utcnow()
            milestone_found = True
            updated_milestone = m
            break
    
    if not milestone_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Milestone with id {milestone_id} not found in project {project_id}"
        )
    
    # Update project in database
    project_collection.update_one(
        {"id": normalized_project_id},
        {"$set": {"milestones": milestones, "updated_at": datetime.utcnow()}}
    )
    
    return {
        "success": True,
        "message": f"Milestone status updated to '{new_status}'",
        "data": {
            "project_id": normalized_project_id,
            "milestone_id": milestone_id,
            "milestone": updated_milestone
        }
    }


@project_router.get("/chat_participants/{project_id}")
async def get_project_chat_participants(
    project_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get list of all participants (students, mentors, counsellor) for project chat.
    
    Returns user details of all assigned students, mentors, and counsellor for the project.
    """
    token = credentials.credentials
    user_collection = get_user_collection()
    project_collection = get_project_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    requested_email = user.get("email")
    
    # Normalize project_id to int when possible
    try:
        if isinstance(project_id, str) and project_id.isdigit():
            normalized_project_id = int(project_id)
        else:
            normalized_project_id = project_id
    except Exception:
        normalized_project_id = project_id
    
    project = project_collection.find_one({"id": normalized_project_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found"
        )
    
    participants = {
        "students": [],
        "mentors": [],
        "counsellor": None
    }
    
    # Get assigned students
    assigned_students = project.get("assigned_student", []) or []
    for student in assigned_students:
        student_id = student.get("id") if isinstance(student, dict) else student
        if student_id:
            try:
                student_user = user_collection.find_one({"_id": ObjectId(student_id)})
                if student_user:
                    participants["students"].append({
                        "_id": str(student_user.get("_id")),
                        "id": student_user.get("id"),
                        "full_name": student_user.get("full_name"),
                        "email": student_user.get("email"),
                        "profile_photo": student_user.get("profile_photo"),
                        "user_role": student_user.get("user_role")
                    })
            except Exception:
                continue
    
    # Get assigned mentors
    assigned_mentors = project.get("assigned_mentor", []) or []
    
    # Handle both formats: single dict or list of dicts
    if isinstance(assigned_mentors, dict):
        assigned_mentors = [assigned_mentors]
    
    for mentor in assigned_mentors:
        mentor_id = mentor.get("id") if isinstance(mentor, dict) else mentor
        if mentor_id:
            try:
                mentor_user = user_collection.find_one({"_id": ObjectId(mentor_id)})
                if mentor_user:
                    participants["mentors"].append({
                        "_id": str(mentor_user.get("_id")),
                        "id": mentor_user.get("id"),
                        "full_name": mentor_user.get("full_name"),
                        "email": mentor_user.get("email"),
                        "profile_photo": mentor_user.get("profile_photo"),
                        "user_role": mentor_user.get("user_role")
                    })
            except Exception:
                continue
    
    # Get counsellor from created_by_email
    counsellor_email = project.get("created_by_email")
    if counsellor_email:
        counsellor_user = user_collection.find_one({"email": counsellor_email})
        if counsellor_user:
            participants["counsellor"] = {
                "_id": str(counsellor_user.get("_id")),
                "id": counsellor_user.get("id"),
                "full_name": counsellor_user.get("full_name"),
                "email": counsellor_user.get("email"),
                "profile_photo": counsellor_user.get("profile_photo"),
                "user_role": counsellor_user.get("user_role")
            }
    
    return {
        "success": True,
        "message": f"Chat participants for project {project_id} retrieved successfully",
        "data": {
            "project_id": normalized_project_id,
            "project_title": project.get("title"),
            "requested_by_email": requested_email,
            "participants": participants
        }
    }