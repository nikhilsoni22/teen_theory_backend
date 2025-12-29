from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.database import get_meetings_collection, get_user_collection
from models.meeting_model import MentorMeetings
from datetime import datetime
from typing import Optional

meeting_router = APIRouter(prefix="/meetings", tags=["Meetings"])
security = HTTPBearer()

# CREATE MEETING API ENDPOINT........................
@meeting_router.post('/create')
async def create_meeting(payload: dict = Body(...), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Create a meeting. `link_created_by` is taken from the bearer token's user email.

    This function now handles database availability errors and returns
    a 500 response if the DB is not reachable.
    """
    token = credentials.credentials
    # Resolve collections lazily and guard against missing DB connection
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Validate required fields
    title = payload.get('title')
    date_time = payload.get('date_time')
    meeting_link = payload.get('meeting_link')

    if not title or not date_time or not meeting_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`title`, `date_time` and `meeting_link` are required")

    meeting_doc = {
        "project_name": payload.get('project_name'),
        "link_created_by": user.get('email'),
        "title": title,
        "date_time": date_time,
        "meeting_link": meeting_link,
        "project_counsellor_email": payload.get('project_counsellor_email'),
        "project_mentor": payload.get('project_mentor'),
        "status": payload.get('status', 'pending'),
        "created_at": datetime.utcnow()
    }

    try:
        result = meetings_collection.insert_one(meeting_doc)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save meeting: {e}")

    meeting_doc["_id"] = str(result.inserted_id)

    return {"success": True, "message": "Meeting created successfully", "data": meeting_doc}


@meeting_router.post('/request')
async def request_meeting(payload: dict = Body(...), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Create a meeting request. The requesting user's email is set in `request_by_meeting` (from token).

    Required payload fields: `title`, `date_time`, `mentor`, `counsellor`.
    Optional: `project_name`, `message`.
    """
    token = credentials.credentials
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    title = payload.get('title')
    mentor = payload.get('mentor')
    counsellor = payload.get('counsellor')

    if not title or not mentor or not counsellor:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`title`, `mentor` and `counsellor` are required")

    meeting_doc = {
        "project_name": payload.get('project_name'),
        "request_by_meeting": user.get('email'),
        "title": title,
        "mentor": mentor,
        "counsellor": counsellor,
        "message": payload.get('message'),
        "status": payload.get('status', 'requested'),
        "created_at": datetime.utcnow()
    }

    try:
        result = meetings_collection.insert_one(meeting_doc)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save meeting request: {e}")

    meeting_doc["_id"] = str(result.inserted_id)

    return {"success": True, "message": "Meeting request created successfully", "data": meeting_doc}

# GET ALL MEETINGS API ENDPOINT........................
@meeting_router.get('/all_meetings')
async def get_all_meetings():
    """Return all meetings. ObjectIds are converted to strings for JSON serialisation."""
    try:
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    try:
        meetings = list(meetings_collection.find().sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meetings: {e}")

    for m in meetings:
        m["_id"] = str(m.get("_id"))

    return {"success": True, "message": "Meetings retrieved successfully", "data": meetings}


# GET MY MEETINGS API ENDPOINT........................
@meeting_router.get('/mine')
async def get_my_meetings(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return meetings created by the authenticated user (uses token -> user email)."""
    token = credentials.credentials
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        meetings = list(meetings_collection.find({"link_created_by": user.get('email')}).sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meetings: {e}")

    for m in meetings:
        m["_id"] = str(m.get("_id"))

    return {"success": True, "message": "User meetings retrieved successfully", "data": meetings}


@meeting_router.post('/mentor_create_meeting')
async def create_mentor_meeting(payload: MentorMeetings = Body(...), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Create a mentor-type meeting. Uses token to set `link_created_by`."""
    token = credentials.credentials
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Build meeting document from MentorMeetings model
    meeting_doc = {
        "meeting_type": payload.meeting_type,
        "assigned_students": payload.assigned_students,
        "date_time": payload.date_time,
        "duration": payload.duration,
        "purpose": payload.purpose,
        "meeting_link": payload.meeting_link,
        "link_created_by": user.get("email"),
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    try:
        result = meetings_collection.insert_one(meeting_doc)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save mentor meeting: {e}")

    meeting_doc["_id"] = str(result.inserted_id)
    return {"success": True, "message": "Mentor meeting created", "data": meeting_doc}


@meeting_router.get('/by_student')
async def get_meetings_by_student(email: str = None):
    """Return meetings where `assigned_students` contains the provided email.

    The endpoint tolerates `assigned_students` stored as:
    - list of emails
    - comma-separated string
    - single string
    """
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`email` query parameter is required")

    try:
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    try:
        meetings = list(meetings_collection.find().sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meetings: {e}")

    matched = []
    for m in meetings:
        # Try common keys
        assigned = m.get("assigned_students") if m.get("assigned_students") is not None else m.get("Assigned_students")
        if assigned is None:
            continue

        candidates = []
        if isinstance(assigned, list):
            candidates = [str(x).strip() for x in assigned if x is not None]
        elif isinstance(assigned, str):
            # comma-separated or single
            if "," in assigned:
                candidates = [s.strip() for s in assigned.split(",") if s.strip()]
            else:
                candidates = [assigned.strip()]
        else:
            candidates = [str(assigned).strip()]

        if email in candidates:
            m["_id"] = str(m.get("_id"))
            matched.append(m)

    return {"success": True, "message": f"Meetings for student {email} retrieved successfully", "data": matched}


@meeting_router.get('/counsellor_meetings')
async def get_meetings_for_counsellor(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return meetings where `project_counsellor_email` equals the authenticated user's email.

    Authentication via Bearer token is required; token is resolved to a user email.
    """
    token = credentials.credentials
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    counsellor_email = user.get('email')

    try:
        meetings = list(meetings_collection.find({"project_counsellor_email": counsellor_email}).sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meetings: {e}")

    for m in meetings:
        m["_id"] = str(m.get("_id"))

    return {"success": True, "message": f"Meetings for counsellor {counsellor_email} retrieved successfully", "data": meetings}


@meeting_router.get('/requests')
async def get_meeting_requests():
    """Return meeting requests (documents that contain `request_by_meeting`).

    For each request, if `mentor` or `counsellor` is an email (or dict with `email`),
    replace it with a small user profile fetched from users collection.
    """
    try:
        meetings_collection = get_meetings_collection()
        user_collection = get_user_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    try:
        # Find meetings that look like requests (have request_by_meeting)
        meetings = list(meetings_collection.find({"request_by_meeting": {"$exists": True}}).sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meeting requests: {e}")

    def resolve_person_field(field):
        # field may be an email string, a dict with email, or already a profile
        if not field:
            return field
        # If it's a dict and already looks like a profile, just convert _id
        if isinstance(field, dict) and field.get("_id"):
            field_copy = dict(field)
            try:
                field_copy["_id"] = str(field_copy.get("_id"))
            except Exception:
                pass
            return field_copy

        email = None
        if isinstance(field, str) and "@" in field:
            email = field
        elif isinstance(field, dict) and field.get("email"):
            email = field.get("email")

        if email:
            person = user_collection.find_one({"email": email})
            if person:
                return {
                    "_id": str(person.get("_id")),
                    "id": person.get("id"),
                    "full_name": person.get("full_name"),
                    "email": person.get("email"),
                    "profile_photo": person.get("profile_photo"),
                    "user_role": person.get("user_role")
                }

        # Fallback: return original field
        return field

    for m in meetings:
        m["_id"] = str(m.get("_id"))
        # resolve mentor and counsellor
        try:
            m["mentor"] = resolve_person_field(m.get("mentor"))
        except Exception:
            pass
        try:
            m["counsellor"] = resolve_person_field(m.get("counsellor"))
        except Exception:
            pass
        # resolve request_by_meeting (the requester email -> user profile)
        try:
            m["request_by_meeting"] = resolve_person_field(m.get("request_by_meeting"))
        except Exception:
            pass

    return {"success": True, "message": "Meeting requests retrieved successfully", "data": meetings}


@meeting_router.get('/requests/mine')
async def get_my_meeting_requests(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return meeting requests where the authenticated user's email matches mentor or counsellor.

    Matching is tolerant: `mentor`/`counsellor` fields may be stored as an email string
    or as a dict containing an `email` key.
    """
    token = credentials.credentials
    try:
        user_collection = get_user_collection()
        meetings_collection = get_meetings_collection()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database not available: {e}")

    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    email = user.get('email')
    if not email:
        return {"success": True, "message": "Authenticated user has no email", "data": []}

    try:
        # Match mentor or counsellor stored as string or nested email
        query = {
            "$or": [
                {"mentor": email},
                {"mentor.email": email},
                {"counsellor": email},
                {"counsellor.email": email}
            ]
        }
        meetings = list(meetings_collection.find(query).sort("created_at", -1))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch meeting requests: {e}")

    def resolve_person_field(field):
        if not field:
            return field
        if isinstance(field, dict) and field.get("_id"):
            field_copy = dict(field)
            try:
                field_copy["_id"] = str(field_copy.get("_id"))
            except Exception:
                pass
            return field_copy

        email_val = None
        if isinstance(field, str) and "@" in field:
            email_val = field
        elif isinstance(field, dict) and field.get("email"):
            email_val = field.get("email")

        if email_val:
            person = user_collection.find_one({"email": email_val})
            if person:
                return {
                    "_id": str(person.get("_id")),
                    "id": person.get("id"),
                    "full_name": person.get("full_name"),
                    "email": person.get("email"),
                    "profile_photo": person.get("profile_photo"),
                    "user_role": person.get("user_role")
                }

        return field

    for m in meetings:
        m["_id"] = str(m.get("_id"))
        try:
            m["mentor"] = resolve_person_field(m.get("mentor"))
        except Exception:
            pass
        try:
            m["counsellor"] = resolve_person_field(m.get("counsellor"))
        except Exception:
            pass
        # resolve request_by_meeting to profile when possible
        try:
            m["request_by_meeting"] = resolve_person_field(m.get("request_by_meeting"))
        except Exception:
            pass

    return {"success": True, "message": "My meeting requests retrieved successfully", "data": meetings}