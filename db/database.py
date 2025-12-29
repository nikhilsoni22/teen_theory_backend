from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: MongoClient = None
    
    @classmethod
    def connect_db(cls):
        try:
            # Simplified connection for Python 3.13 compatibility
            cls.client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=20000,
                socketTimeoutMS=20000,
            )
            
            # Test connection
            cls.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB!")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            # Don't raise the error, just log it and continue
            logger.warning("Server starting without database connection. Database will be unavailable.")
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            logger.warning("Server starting without database connection. Database will be unavailable.")
    
    @classmethod
    def close_db(cls):
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_db(cls):
        if cls.client is None:
            logger.error("Database client is not initialized!")
            raise Exception("Database connection not established")
        return cls.client[settings.DATABASE_NAME]

# Database collections
def get_database():
    return Database.get_db()

def get_admin_collection():
    db = get_database()
    return db["admins"]

def get_user_collection():
    db = get_database()
    return db["users"]

def get_project_collection():
    db = get_database()
    return db["projects"]
    
def get_ticket_collection():
    db = get_database()
    return db["tickets"]

def get_meetings_collection():
    db = get_database()
    return db["meetings"]

def get_chats_collection():
    db = get_database()
    return db["chats"]

def get_conversation_collection():
    db = get_database()
    return db["conversations"]