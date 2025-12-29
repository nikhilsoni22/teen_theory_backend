"""Script to create a test user in the database"""
from db.database import Database, get_user_collection
from utils.auth import get_password_hash
from datetime import datetime

# Connect to database
Database.connect_db()

user_collection = get_user_collection()

# Check if user already exists
existing_user = user_collection.find_one({"email": "admin@example.com"})

if existing_user:
    print("User already exists!")
    print(f"ID: {existing_user['id']}")
    print(f"Name: {existing_user['name']}")
    print(f"Email: {existing_user['email']}")
else:
    # Create test user
    test_user = {
        "id": 1,
        "email": "admin@example.com",
        "name": "Demo Admin",
        "hashed_password": get_password_hash("123456"),
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    user_collection.insert_one(test_user)
    print("Test user created successfully!")
    print(f"Email: admin@example.com")
    print(f"Password: 123456")

# Close database connection
Database.close_db()
