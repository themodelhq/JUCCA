from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, AsyncGenerator
import pandas as pd
import tempfile
import os
import time
import json

from app.core.database import get_db, engine, Base
from app.models import User, BlacklistedKeyword, RestrictedBrand, ProhibitedProduct, ChatHistory
from app.schemas import ChatRequest, ChatResponse, UserCreate, UserLogin, PolicyStats
from app.services.policy_engine import PolicyEngine
from app.services.llm_service import (
    generate_explanation, 
    generate_explanation_streaming,
    llm_service
)
from app.services.nlp_entities import extract_entities
from app.services.memory import get_memory, update_memory
from app.services.auth_service import (
    authenticate_user, get_password_hash, create_access_token, decode_token
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="JUCCA API",
    description="Jumia Content Compliance Assistant - Conversational Compliance System with GPT4All",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Request tracking for metrics
request_count = 0
request_times = []

# Dependency to get current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ============================================
# Authentication Endpoints
# ============================================

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    global request_count
    request_count += 1
    
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@app.post("/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    global request_count
    request_count += 1
    
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role
    )
    db.add(user)
    db.commit()
    return {"message": "User created successfully"}


# ============================================
# Compliance Endpoints
# ============================================

@app.post("/ask", response_model=ChatResponse)
async def ask_compliance_question(
    q: ChatRequest, 
    db: Session = Depends(get_db)
):
    """Main endpoint for compliance questions with streaming support."""
    global request_count, request_times
    start_time = time.time()
    request_count += 1
    
    # Get session memory
    memory = get_memory(q.session_id)
    
    # Extract entities from question
    entities = extract_entities(q.question)
    
    # Apply memory context if available
    category = entities.get("category") or memory.get("category")
    country = entities.get("country") or memory.get("country")
    
    # Update memory
    update_memory(q.session_id, {
        "brand": entities.get("brand"),
        "category": category,
        "country": country
    })
    
    # Run compliance check
    policy_engine = PolicyEngine(db)
    result = policy_engine.check_compliance(
        q.question, 
        country=country, 
        category=category
    )
    
    # Generate LLM explanation
    answer = generate_explanation(
        question=q.question,
        decision=result["decision"],
        reason=result["reason"],
        role=q.role,
        detected_entities=entities
    )
    
    # Save to chat history
    chat = ChatHistory(
        session_id=q.session_id,
        question=q.question,
        decision=result["decision"],
        reason=result["reason"]
    )
    db.add(chat)
    db.commit()
    
    # Track request time
    elapsed = time.time() - start_time
    request_times.append(elapsed)
    if len(request_times) > 1000:
        request_times = request_times[-1000:]
    
    return ChatResponse(
        decision=result["decision"],
        reason=result["reason"],
        answer=answer,
        entities=entities
    )

@app.post("/ask/stream")
async def ask_compliance_question_streaming(
    q: ChatRequest,
    db: Session = Depends(get_db)
):
    """Streaming endpoint for compliance questions."""
    global request_count
    request_count += 1
    
    # Get session memory
    memory = get_memory(q.session_id)
    
    # Extract entities
    entities = extract_entities(q.question)
    
    # Apply memory context
    category = entities.get("category") or memory.get("category")
    country = entities.get("country") or memory.get("country")
    
    # Update memory
    update_memory(q.session_id, {
        "brand": entities.get("brand"),
        "category": category,
        "country": country
    })
    
    # Run compliance check
    policy_engine = PolicyEngine(db)
    result = policy_engine.check_compliance(
        q.question,
        country=country,
        category=category
    )
    
    # Generate streaming response
    async def generate_stream():
        yield json.dumps({
            "type": "decision",
            "decision": result["decision"],
            "reason": result["reason"],
            "entities": entities
        }) + "\n"
        
        for chunk in generate_explanation_streaming(
            question=q.question,
            decision=result["decision"],
            reason=result["reason"],
            role=q.role,
            detected_entities=entities
        ):
            yield json.dumps({"type": "content", "chunk": chunk}) + "\n"
        
        yield json.dumps({"type": "done"}) + "\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


# ============================================
# Admin Endpoints
# ============================================

@app.post("/admin/upload-policy")
async def upload_policy(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process policy Excel file."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Process the file
        policy_engine = PolicyEngine(db)
        results = policy_engine.rebuild_from_excel(tmp_path)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

@app.get("/admin/policy-stats", response_model=PolicyStats)
async def get_policy_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get policy statistics."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return PolicyStats(
        total_brands=db.query(RestrictedBrand).count(),
        total_keywords=db.query(BlacklistedKeyword).count(),
        total_products=db.query(ProhibitedProduct).count()
    )

@app.delete("/admin/cache")
async def clear_cache(
    current_user: User = Depends(get_current_user)
):
    """Clear the LLM response cache."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    llm_service.clear_cache()
    return {"status": "success", "message": "Cache cleared"}


# ============================================
# Monitoring & Health Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy", 
        "service": "JUCCA API",
        "version": "1.1.0"
    }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with component status."""
    from app.services.llm_service import gpt4all_manager, cloud_client, load_manager
    
    # Check components
    components = {
        "database": "healthy",
        "gpt4all": "healthy" if gpt4all_manager.is_healthy() else "unavailable",
        "cloud_fallback": "available" if cloud_client.is_available() else "unavailable",
        "cache": "healthy"
    }
    
    # Overall status
    overall = "healthy"
    for status in components.values():
        if status == "unavailable":
            overall = "degraded"
            break
    
    return {
        "status": overall,
        "components": components,
        "version": "1.1.0"
    }

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    global request_count, request_times
    
    # Calculate percentiles
    if request_times:
        sorted_times = sorted(request_times)
        p50 = sorted_times[int(len(sorted_times) * 0.50)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
    else:
        p50 = p95 = p99 = 0
    
    # Get service status
    status = llm_service.get_status()
    
    metrics_text = f"""# HELP jucca_requests_total Total number of requests
# TYPE jucca_requests_total counter
jucca_requests_total {request_count}

# HELP jucca_request_duration_seconds Request duration in seconds
# TYPE jucca_request_duration_seconds histogram
"""
    
    # Add histogram buckets (simplified)
    for threshold in [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]:
        count = sum(1 for t in request_times if t <= threshold)
        metrics_text += f'jucca_request_duration_seconds_bucket{{le="{threshold}"}} {count}\n'
    
    metrics_text += f'jucca_request_duration_seconds_bucket{{le="+Inf"}} {len(request_times)}\n'
    metrics_text += f'jucca_request_duration_seconds_sum {sum(request_times)}\n'
    metrics_text += f'jucca_request_duration_seconds_count {len(request_times)}\n'
    
    # Additional metrics
    metrics_text += f"""
# HELP jucca_cache_size Current cache size
# TYPE jucca_cache_size gauge
jucca_cache_size {status["cache"]["size"]}

# HELP jucca_load_active_requests Active requests
# TYPE jucca_load_active_requests gauge
jucca_load_active_requests {status["load"]["active_requests"]}

# HELP jucca_load_capacity_used_percent Capacity used percentage
# TYPE jucca_load_capacity_used_percent gauge
jucca_load_capacity_used_percent {float(status["load"]["capacity_used"].replace("%", "")) / 100}

# HELP jucca_requests_total_total Total requests
# TYPE jucca_requests_total_total counter
jucca_requests_total_total {status["load"]["total_requests"]}

# HELP jucca_requests_failed_total Failed requests
# TYPE jucca_requests_failed_total counter
jucca_requests_failed_total {status["load"]["failed_requests"]}

# HELP jucca_model_loaded Model loaded status
# TYPE jucca_model_loaded gauge
jucca_model_loaded {1 if status["model"]["loaded"] else 0}
"""
    
    return Response(content=metrics_text, media_type="text/plain")


# ============================================
# Service Status Endpoint
# ============================================

@app.get("/status")
async def service_status():
    """Get detailed service status."""
    status = llm_service.get_status()
    
    return {
        "service": "JUCCA",
        "version": "1.1.0",
        "status": "operational",
        "components": {
            "api": "healthy",
            "database": "healthy",
            "llm": {
                "type": "gpt4all",
                "model": status["model"]["model_name"],
                "status": "loaded" if status["model"]["loaded"] else "not loaded"
            },
            "cache": {
                "enabled": status["config"]["cache_enabled"],
                "size": status["cache"]["size"],
                "ttl_minutes": status["cache"]["ttl_minutes"]
            },
            "cloud_fallback": {
                "enabled": status["config"]["cloud_fallback"],
                "available": status["cloud_available"]
            }
        },
        "load": status["load"],
        "performance": {
            "avg_latency_ms": float(status["load"]["avg_latency_ms"]),
            "success_rate": status["load"]["success_rate"]
        }
    }


# ============================================
# Streaming SSE Endpoint
# ============================================

@app.get("/stream/test")
async def test_stream():
    """Test streaming endpoint."""
    async def generate():
        for i in range(10):
            yield f"data: Message {i}\n\n"
            await asyncio.sleep(0.5)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        workers=2,
        loop="uvloop"
    )
