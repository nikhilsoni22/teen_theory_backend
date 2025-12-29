from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.chat_model import ChatMessage, ChatResponse
from db.database import get_chats_collection, get_user_collection, get_conversation_collection
from datetime import datetime
from bson import ObjectId

chat_router = APIRouter(prefix="/chat", tags=["Chat"])
security = HTTPBearer()

@chat_router.post("/send", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    chat: ChatMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send a chat message in a project context."""
    token = credentials.credentials
    user_collection = get_user_collection()
    chat_collection = get_chats_collection()
    conversation_collection = get_conversation_collection()
    
    # Verify sender token
    sender = user_collection.find_one({"token": token})
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    sender_email = sender.get("email")
    
    # Verify receiver exists
    receiver = user_collection.find_one({"email": chat.receiver_email})
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receiver not found"
        )
    
    # Check existing conversation between sender and receiver
    conversation = conversation_collection.find_one({
        "project_id": chat.project_id,
        "members": {"$all": [sender_email, chat.receiver_email]}
    })
    
    if conversation:
        conversation_id = str(conversation["_id"])
    else:
        # Create new conversation
        new_conv = {
            "project_id": chat.project_id,
            "members": [sender_email, chat.receiver_email],
            "created_at": datetime.utcnow()
        }
        conv_result = conversation_collection.insert_one(new_conv)
        conversation_id = str(conv_result.inserted_id)
    
    # Save message
    chat_dict = {
        "conversation_id": conversation_id,
        "project_id": chat.project_id,
        "sender_email": sender_email,
        "receiver_email": chat.receiver_email,
        "message": chat.message,
        "created_at": datetime.utcnow()
    }
    
    result = chat_collection.insert_one(chat_dict)
    chat_dict["_id"] = str(result.inserted_id)
    
    return {
        "success": True,
        "message": "Message sent successfully",
        "data": chat_dict
    }


@chat_router.get("/messages/{conversation_id}")
async def get_conversation_messages(
    conversation_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get all messages for a specific conversation with sender and receiver details."""
    token = credentials.credentials
    user_collection = get_user_collection()
    chat_collection = get_chats_collection()
    conversation_collection = get_conversation_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_email = user.get("email")
    
    # Verify conversation exists and user is a member
    try:
        conversation = conversation_collection.find_one({
            "_id": ObjectId(conversation_id)
        })
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID"
        )
    
    if not conversation:
       return {
        "success": False,
        "message": "Conversation not found",
        "data": []
       }
    
    # Check if user is a member of this conversation
    if user_email not in conversation.get("members", []):
        return {
        "success": False,
        "message": "You are not a member of this conversation",
        "data": []
        }
    
    # Get all messages for this conversation
    messages = list(chat_collection.find({
        "conversation_id": conversation_id,
        "project_id": conversation.get("project_id")
    }).sort("created_at", 1))
    
    # Enrich messages with sender and receiver details
    enriched_messages = []
    for msg in messages:
        sender_email = msg.get("sender_email")
        receiver_email = msg.get("receiver_email")
        
        # Get sender details
        sender_user = None
        if sender_email:
            sender = user_collection.find_one({"email": sender_email})
            if sender:
                sender_user = {
                    "_id": str(sender.get("_id")),
                    "id": sender.get("id"),
                    "full_name": sender.get("full_name"),
                    "email": sender.get("email"),
                    "profile_photo": sender.get("profile_photo"),
                    "user_role": sender.get("user_role")
                }
        
        # Get receiver details
        receiver_user = None
        if receiver_email:
            receiver = user_collection.find_one({"email": receiver_email})
            if receiver:
                receiver_user = {
                    "_id": str(receiver.get("_id")),
                    "id": receiver.get("id"),
                    "full_name": receiver.get("full_name"),
                    "email": receiver.get("email"),
                    "profile_photo": receiver.get("profile_photo"),
                    "user_role": receiver.get("user_role")
                }
        
        enriched_messages.append({
            "_id": str(msg.get("_id")),
            "conversation_id": conversation_id,
            "project_id": msg.get("project_id"),
            "sender_email": sender_email,
            "sender": sender_user,
            "receiver_email": receiver_email,
            "receiver": receiver_user,
            "message": msg.get("message"),
            "created_at": msg.get("created_at")
        })
    
    return {
        "success": True,
        "message": f"Messages for conversation retrieved successfully",
        "data": enriched_messages
    }


@chat_router.get("/conversation")
async def get_conversation_by_emails(
    user1_email: str,
    user2_email: str,
    project_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Fetch conversation_id between two users by their emails in a project context."""
    token = credentials.credentials
    user_collection = get_user_collection()
    conversation_collection = get_conversation_collection()
    
    # Verify user token
    user = user_collection.find_one({"token": token})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_email = user.get("email")
    
    # Check if requesting user is one of the participants
    if user_email not in [user1_email, user2_email]:
        return {
            "success": False,
            "message": "You are not authorized to access this conversation",
            "data": None
        }
    # Try to find conversation using different possible project_id types
    candidate_project_values = [project_id]
    # Try ObjectId if possible
    try:
        candidate_project_values.append(ObjectId(project_id))
    except Exception:
        pass

    # Try integer if project_id looks numeric
    try:
        if str(project_id).isdigit():
            candidate_project_values.append(int(project_id))
    except Exception:
        pass

    conversation = None
    for pid in candidate_project_values:
        conversation = conversation_collection.find_one({
            "project_id": pid,
            "members": {"$all": [user1_email, user2_email]}
        })
        if conversation:
            break

    if conversation:
        return {
            "success": True,
            "message": "Conversation found",
            "data": {
                "conversation_id": str(conversation["_id"]),
                "project_id": conversation.get("project_id"),
                "members": conversation.get("members"),
                "created_at": conversation.get("created_at"),
                "exists": True
            }
        }

    # If not found, attempt a cross-project lookup (helpful if project_id types don't match)
    fallback = conversation_collection.find_one({
        "members": {"$all": [user1_email, user2_email]}
    })
    if fallback:
        return {
            "success": True,
            "message": "Conversation exists but project_id mismatch detected. Returning found conversation info.",
            "data": {
                "conversation_id": str(fallback.get("_id")),
                "project_id": fallback.get("project_id"),
                "members": fallback.get("members"),
                "created_at": fallback.get("created_at"),
                "exists": True,
                "note": "This conversation is in a different project or stored with a different project_id type."
            }
        }

    # No conversation at all
    return {
        "success": False,
        "message": "No conversation exists between yours",
        "data": {
            "conversation_id": None,
            "project_id": project_id,
            "members": [user1_email, user2_email],
            "exists": False
        }
    }