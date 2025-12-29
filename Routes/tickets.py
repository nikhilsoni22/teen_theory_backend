from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.database import get_ticket_collection, get_user_collection
from models.ticket_model import TicketModel
from typing import List, Optional
from datetime import datetime
import os
import shutil
import secrets
from bson.objectid import ObjectId

ticket_router = APIRouter(prefix="/tickets", tags=["Tickets"])
security = HTTPBearer()


@ticket_router.post("/create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    title: str = Form(...),
    project_name: str = Form(...),
    priority: str = Form(...),
    explaination: str = Form(...),
    attachments: Optional[List[UploadFile]] = File(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a ticket (multipart/form-data). `raised_by` is set from the caller's token."""
    token = credentials.credentials
    user_collection = get_user_collection()
    ticket_collection = get_ticket_collection()

    # Resolve user by token
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    raised_by_email = user.get("email")

    # Handle file attachments
    attachment_paths: List[str] = []
    if attachments:
        upload_dir = "uploads/ticket_attachments"
        os.makedirs(upload_dir, exist_ok=True)
        for up in attachments:
            try:
                ext = os.path.splitext(up.filename)[1]
                fname = f"ticket_{secrets.token_hex(8)}{ext}"
                dest = os.path.join(upload_dir, fname)
                with open(dest, "wb") as f:
                    shutil.copyfileobj(up.file, f)
                attachment_paths.append(f"/{dest.replace(os.sep, '/')}")
            except Exception:
                # skip problematic files but continue
                continue

    ticket_doc = {
        "title": title,
        "raised_by": raised_by_email,
        "project_name": project_name,
        "assigned_to": None,
        "priority": priority,
        "explaination": explaination,
        "attachments": attachment_paths,
        "status": "Pending",
    }

    result = ticket_collection.insert_one(ticket_doc)
    ticket_doc["_id"] = str(result.inserted_id)

    ticket_model = TicketModel(**ticket_doc)
    try:
        ticket_data = ticket_model.model_dump(by_alias=True)
    except Exception:
        ticket_data = ticket_model.dict()

    return {
        "success": True,
        "message": "Ticket created successfully",
        "data": ticket_data,
    }


@ticket_router.get("/all_tickets")
async def get_all_tickets():
    """Return all tickets."""
    ticket_collection = get_ticket_collection()
    tickets = list(ticket_collection.find())
    user_collection = get_user_collection()

    # Convert ObjectId to string for each ticket
    out = []
    for t in tickets:
        t_copy = dict(t)
        t_copy["_id"] = str(t_copy.get("_id"))
        # Ensure attachments exists
        t_copy["attachments"] = t_copy.get("attachments", [])
        # Attach raised_by user data (sanitized)
        raised_by_email = t_copy.get("raised_by")
        raised_user = None
        if raised_by_email:
            try:
                user = user_collection.find_one({"email": raised_by_email})
                if user:
                    raised_user = {
                        "_id": str(user.get("_id")),
                        "id": user.get("id"),
                        "full_name": user.get("full_name"),
                        "email": user.get("email"),
                        "profile_photo": user.get("profile_photo"),
                        "user_role": user.get("user_role"),
                        "phone_number": user.get("phone_number"),
                        "created_at": user.get("created_at")
                    }
            except Exception:
                raised_user = None

        t_copy["raised_by_user"] = raised_user
        out.append(t_copy)

    return {
        "success": True,
        "message": "Tickets retrieved successfully",
        "data": out,
    }


@ticket_router.put("/update_status/{ticket_id}", response_model=dict)
async def update_ticket_status(ticket_id: str, status: str = Form(...), message: Optional[str] = Form(None), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Update the status of a ticket. Requires Authorization Bearer token."""
    token = credentials.credentials
    user_collection = get_user_collection()
    ticket_collection = get_ticket_collection()

    # Verify requester
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Validate ObjectId
    try:
        oid = ObjectId(ticket_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ticket id")

    # Update status and append status history entry
    history_entry = {
        "status": status,
        "message": message,
        "changed_by": user.get("email"),
        "changed_at": datetime.utcnow()
    }

    result = ticket_collection.update_one({"_id": oid}, {"$set": {"status": status}, "$push": {"status_history": history_entry}})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    # Return updated ticket
    ticket = ticket_collection.find_one({"_id": oid})
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found after update")

    ticket_copy = dict(ticket)
    ticket_copy["_id"] = str(ticket_copy.get("_id"))
    ticket_copy["attachments"] = ticket_copy.get("attachments", [])

    # Attach raised_by user data (sanitized)
    raised_by_email = ticket_copy.get("raised_by")
    raised_user = None
    if raised_by_email:
        try:
            u = user_collection.find_one({"email": raised_by_email})
            if u:
                raised_user = {
                    "_id": str(u.get("_id")),
                    "id": u.get("id"),
                    "full_name": u.get("full_name"),
                    "email": u.get("email"),
                    "profile_photo": u.get("profile_photo"),
                    "user_role": u.get("user_role"),
                    "phone_number": u.get("phone_number"),
                    "created_at": u.get("created_at")
                }
        except Exception:
            raised_user = None

    ticket_copy["raised_by_user"] = raised_user

    return {
        "success": True,
        "message": "Ticket status updated successfully",
        "data": ticket_copy,
    }
    
    
    