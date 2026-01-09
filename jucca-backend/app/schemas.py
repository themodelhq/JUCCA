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

    class Config:
        from_attributes = True

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
