from pydantic import BaseModel
from typing import Optional, List

# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "seller"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class UserCreateResponse(BaseModel):
    id: int
    username: str
    role: str

class LogResponse(BaseModel):
    id: int
    level: str
    category: str
    message: str
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class LogQuery(BaseModel):
    level: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 100
    offset: int = 0

# Chat schemas
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    role: str = "seller"

class ChatResponse(BaseModel):
    decision: str
    reason: str
    answer: str
    entities: dict

# Policy schemas
class PolicyUpload(BaseModel):
    file_path: Optional[str] = None

class PolicyStats(BaseModel):
    total_brands: int
    total_keywords: int
    total_products: int
