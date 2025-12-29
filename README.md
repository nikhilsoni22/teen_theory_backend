# Teen Theory Backend

Backend API for Teen Theory Platform built with FastAPI and MongoDB.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
- Copy `.env.example` to `.env`
- Update the values as needed

3. Run the application:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
teen_theory_backend/
├── db/
│   └── database.py          # Database connection and collections
├── models/
│   └── user_model.py        # Pydantic models for users
├── Routes/
│   └── auth_routes.py       # Authentication routes
├── utils/
│   └── auth.py              # Authentication utilities
├── main.py                  # FastAPI application
├── config.py                # Configuration settings
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables (not in git)
```

## API Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login and get access token
- `GET /auth/me` - Get current user info

## Environment Variables

- `MONGODB_URI` - MongoDB connection string
- `DATABASE_NAME` - Database name
- `SECRET_KEY` - JWT secret key
- `ALGORITHM` - JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time (default: 30)
