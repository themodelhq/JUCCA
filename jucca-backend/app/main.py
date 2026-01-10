"""
JUCCA Backend - Jumia Content Compliance Assistant
FastAPI application with GPT4All integration

This file uses RELATIVE imports to ensure compatibility with Render deployment.
"""

import sys
import os
from pathlib import Path

# Ensure the app directory is in the path
# This allows imports to work regardless of PYTHONPATH setting
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Now use relative imports (with .) which work regardless of PYTHONPATH
from .core.database import get_db, engine, Base
from .models import User, BlacklistedKeyword, RestrictedBrand, ProhibitedProduct, ChatHistory, SystemLog
from .schemas import ChatRequest, ChatResponse, UserCreate, UserLogin, UserUpdate, UserResponse, PolicyStats, LogResponse, LogQuery
from .services.policy_engine import PolicyEngine
from .services.llm_service import (
    generate_explanation, 
    generate_explanation_streaming,
    llm_service
)
from .services.nlp_entities import extract_entities
from .services.memory import get_memory, update_memory
from .services.auth_service import (
    authenticate_user, get_password_hash, create_access_token, decode_token
)

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, AsyncGenerator
import pandas as pd
import tempfile
import time
import json

# Create tables
Base.metadata.create_all(bind=engine)

# Create default users if they don't exist
def create_default_users():
    """Create or reset default admin and seller accounts."""
    from .services.auth_service import get_password_hash
    from sqlalchemy.orm import Session
    from .core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            # Update existing admin with correct password
            admin.password_hash = get_password_hash("admin123")
            admin.role = "admin"
            print("Updated existing admin account: admin/admin123")
        else:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin)
            print("Created default admin account: admin/admin123")
        
        # Check if seller exists
        seller = db.query(User).filter(User.username == "seller").first()
        if seller:
            # Update existing seller with correct password
            seller.password_hash = get_password_hash("seller123")
            seller.role = "seller"
            print("Updated existing seller account: seller/seller123")
        else:
            seller = User(
                username="seller",
                password_hash=get_password_hash("seller123"),
                role="seller"
            )
            db.add(seller)
            print("Created default seller account: seller/seller123")
        
        db.commit()
        print("Default users initialized successfully")
    except Exception as e:
        print(f"Error creating default users: {e}")
        db.rollback()
    finally:
        db.close()

# Initialize default users
create_default_users()

# Create default policy data if database is empty
POLICY_DATA_VERSION = "2.4.1"

def initialize_default_policies():
    """Initialize default policy data from JSON file - handles both old and new formats with version checking."""
    from sqlalchemy.orm import Session
    from .core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # Check if we need to reload based on version
        policy_file = Path(__file__).parent.parent / "data" / "policy_data.json"
        if not policy_file.exists():
            print("Policy data file not found")
            db.close()
            return
        
        with open(policy_file, 'r') as f:
            policy_data = json.load(f)
        
        # Check if we need to reload based on version
        json_version = policy_data.get("version", "1.0")
        existing_keywords = db.query(BlacklistedKeyword).count()
        existing_brands = db.query(RestrictedBrand).count()
        
        # Always reload comprehensive policy data (version 2.0+) if database has old format data
        # This ensures the new comprehensive data is always loaded on restart
        needs_reload = False
        
        # Check if version has changed by comparing with the constant
        # If the JSON version is different from the expected version, we need to reload
        current_expected_version = POLICY_DATA_VERSION  # This is "2.4"
        
        # Calculate expected counts from JSON
        blacklisted_keywords = policy_data.get("blacklisted_keywords", {})
        restricted_brands = policy_data.get("restricted_brands", {})
        
        # Count unique keywords in the new format
        expected_keyword_count = 0
        if isinstance(blacklisted_keywords, dict):
            for keywords in blacklisted_keywords.values():
                if isinstance(keywords, list):
                    expected_keyword_count += len(keywords)
        
        # Count brands in the new format
        expected_brand_count = 0
        if isinstance(restricted_brands, dict):
            for category_data in restricted_brands.values():
                if isinstance(category_data, dict):
                    brands = category_data.get("brands", {})
                    if isinstance(brands, dict):
                        expected_brand_count += len(brands)
                    elif isinstance(brands, list):
                        expected_brand_count += len(brands)
        
        if existing_keywords == 0:
            print("Database is empty, loading comprehensive policy data...")
            needs_reload = True
        elif json_version != current_expected_version:
            # Version mismatch - reload to ensure we have the correct data
            print(f"Version mismatch: JSON={json_version}, Expected={current_expected_version}")
            print(f"Reloading comprehensive policy data...")
            needs_reload = True
        elif expected_keyword_count > 0 and existing_keywords < (expected_keyword_count * 0.8):
            # Data appears incomplete (less than 80% of expected keywords)
            print(f"Data incomplete: found {existing_keywords} keywords, expected ~{expected_keyword_count}")
            print(f"Reloading comprehensive policy data...")
            needs_reload = True
        elif json_version.startswith("2.") and existing_keywords < 500:
            # Version 2.x format and we don't have comprehensive data yet
            print(f"Reloading comprehensive policy data (found {existing_keywords} old records)...")
            needs_reload = True
        else:
            print(f"Policy data current ({existing_keywords} keywords, {existing_brands} brands, version {json_version}). No reload needed.")
            db.close()
            return
        
        if not needs_reload:
            db.close()
            return
        
        # Clear existing data if this is a reload (not initial load)
        if existing_keywords > 0:
            print("Clearing existing policy data...")
            db.query(BlacklistedKeyword).delete()
            db.query(RestrictedBrand).delete()
            db.query(ProhibitedProduct).delete()
            db.commit()
        
        keywords_count = 0
        brands_count = 0
        products_count = 0
        
        # Parse new comprehensive format
        blacklisted_keywords = policy_data.get("blacklisted_keywords", {})
        restricted_brands = policy_data.get("restricted_brands", {})
        prohibited_products = policy_data.get("prohibited_products", {})
        
        # Handle new format with country-specific keywords
        if isinstance(blacklisted_keywords, dict):
            # New format: {"NG": ["keyword1", "keyword2"], "KE": [...]}
            # Collect unique keywords with their countries
            keyword_countries = {}  # {"keyword": ["NG", "KE", ...]}
            
            for country, keywords in blacklisted_keywords.items():
                if isinstance(keywords, list):
                    for kw in keywords:
                        kw_lower = kw.strip().lower()
                        if kw_lower not in keyword_countries:
                            keyword_countries[kw_lower] = []
                        if country not in keyword_countries[kw_lower]:
                            keyword_countries[kw_lower].append(country)
            
            # Add each unique keyword once
            for kw_lower, countries in keyword_countries.items():
                existing = db.query(BlacklistedKeyword).filter(
                    BlacklistedKeyword.keyword == kw_lower
                ).first()
                if not existing:
                    keyword = BlacklistedKeyword(
                        keyword=kw_lower,
                        severity="high",
                        scope=",".join(sorted(countries)),
                        description=f"Blacklisted in: {', '.join(sorted(countries))}"
                    )
                    db.add(keyword)
                    keywords_count += 1
        elif isinstance(blacklisted_keywords, list):
            # Old format: [{"keyword": "...", "severity": "...", ...}]
            for item in blacklisted_keywords:
                keyword = BlacklistedKeyword(
                    keyword=item.get("keyword", "").strip().lower(),
                    severity=item.get("severity", "high"),
                    scope=item.get("scope", "global"),
                    description=item.get("description")
                )
                db.add(keyword)
                keywords_count += 1
        
        # Handle new format with nested brand categories
        if isinstance(restricted_brands, dict):
            for category_key, category_data in restricted_brands.items():
                if isinstance(category_data, dict):
                    description = category_data.get("description", "")
                    
                    # Handle nested brands object
                    brands_data = category_data.get("brands", {})
                    if isinstance(brands_data, dict):
                        for brand_name, brand_info in brands_data.items():
                            if isinstance(brand_info, dict):
                                restriction_type = brand_info.get("restriction_type", "restricted")
                                note = brand_info.get("note", description)
                                
                                # Check if brand already exists
                                existing = db.query(RestrictedBrand).filter(
                                    RestrictedBrand.brand == brand_name.strip()
                                ).first()
                                if not existing:
                                    brand = RestrictedBrand(
                                        brand=brand_name.strip(),
                                        category=category_key,
                                        country=None,
                                        status=restriction_type.lower().replace(" ", "_"),
                                        condition=note
                                    )
                                    db.add(brand)
                                    brands_count += 1
                    
                    # Handle simple brands array
                    elif isinstance(brands_data, list):
                        for brand_name in brands_data:
                            if isinstance(brand_name, str):
                                existing = db.query(RestrictedBrand).filter(
                                    RestrictedBrand.brand == brand_name.strip()
                                ).first()
                                if not existing:
                                    brand = RestrictedBrand(
                                        brand=brand_name.strip(),
                                        category=category_key,
                                        country=None,
                                        status="restricted",
                                        condition=description
                                    )
                                    db.add(brand)
                                    brands_count += 1
                    
                    # Handle brands with country restrictions
                    elif isinstance(brands_data, dict):
                        for brand_name, brand_info in brands_data.items():
                            if isinstance(brand_info, dict) and "countries" in brand_info:
                                restriction_type = brand_info.get("restriction_type", "restricted")
                                note = brand_info.get("note", description)
                                
                                existing = db.query(RestrictedBrand).filter(
                                    RestrictedBrand.brand == brand_name.strip()
                                ).first()
                                if not existing:
                                    brand = RestrictedBrand(
                                        brand=brand_name.strip(),
                                        category=category_key,
                                        country=None,
                                        status=restriction_type.lower().replace(" ", "_"),
                                        condition=note
                                    )
                                    db.add(brand)
                                    brands_count += 1
        
        elif isinstance(restricted_brands, list):
            # Old format: [{"brand": "...", "category": "...", ...}]
            for item in restricted_brands:
                brand = RestrictedBrand(
                    brand=item.get("brand", "").strip(),
                    category=item.get("category"),
                    country=item.get("country"),
                    status=item.get("status", "restricted"),
                    condition=item.get("condition")
                )
                db.add(brand)
                brands_count += 1
        
        # Handle new format with nested product rules
        if isinstance(prohibited_products, dict):
            for product_key, product_data in prohibited_products.items():
                if isinstance(product_data, dict):
                    product_name = product_data.get("name", product_key)
                    rules = product_data.get("rules", {})
                    
                    # Handle simple "Blocked" or "Open" status for all countries
                    if isinstance(rules, dict):
                        for country, status in rules.items():
                            if status and status.strip():
                                # Determine if blocked
                                is_blocked = "blocked" in status.lower()
                                
                                existing = db.query(ProhibitedProduct).filter(
                                    ProhibitedProduct.keyword == product_name.lower(),
                                    ProhibitedProduct.country == country
                                ).first()
                                if not existing:
                                    product = ProhibitedProduct(
                                        keyword=product_name.lower(),
                                        category=product_key,
                                        country=country,
                                        status="prohibited" if is_blocked else "restricted",
                                        notes=f"{status} in {country}"
                                    )
                                    db.add(product)
                                    products_count += 1
                    
                    # Handle single status for all countries
                    elif isinstance(rules, str):
                        is_blocked = "blocked" in rules.lower()
                        for country in ["NG", "KE", "EG", "MA", "IC", "GH", "UG", "TN", "SN", "DZ", "SA"]:
                            existing = db.query(ProhibitedProduct).filter(
                                ProhibitedProduct.keyword == product_name.lower(),
                                ProhibitedProduct.country == country
                            ).first()
                            if not existing:
                                product = ProhibitedProduct(
                                    keyword=product_name.lower(),
                                    category=product_key,
                                    country=country,
                                    status="prohibited" if is_blocked else "restricted",
                                    notes=rules
                                )
                                db.add(product)
                                products_count += 1
        
        elif isinstance(prohibited_products, list):
            # Old format: [{"keyword": "...", "category": "...", ...}]
            for item in prohibited_products:
                product = ProhibitedProduct(
                    keyword=item.get("keyword", "").strip(),
                    category=item.get("category"),
                    country=item.get("country"),
                    status=item.get("status", "prohibited"),
                    notes=item.get("notes")
                )
                db.add(product)
                products_count += 1
        
        db.commit()
        print(f"✓ Comprehensive policy data loaded successfully:")
        print(f"  - {keywords_count} blacklisted keywords")
        print(f"  - {brands_count} restricted brands")
        print(f"  - {products_count} prohibited products")
        
    except Exception as e:
        print(f"Error initializing default policies: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

# Initialize default policies
initialize_default_policies()

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

# Guest session token (simple token for guest access)
GUEST_TOKEN = "guest_access_token_"

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
# Special Question Handlers
# ============================================

def check_and_add_blacklisted_keyword(db: Session, keyword: str):
    """Check if a keyword exists in blacklist, add it if not, and return whether it was added."""
    keyword_lower = keyword.strip().lower()
    existing = db.query(BlacklistedKeyword).filter(
        BlacklistedKeyword.keyword == keyword_lower
    ).first()
    
    if not existing:
        new_keyword = BlacklistedKeyword(
            keyword=keyword_lower,
            severity="high",
            scope="global",
            description=f"Blacklisted keyword added via compliance check: {keyword_lower}"
        )
        db.add(new_keyword)
        db.commit()
        return True  # Was added
    return False  # Already existed


def get_authorized_brands_list(db: Session):
    """Get list of brands that require authorization."""
    brands = db.query(RestrictedBrand).all()
    
    # Group by brand name and collect their conditions
    brand_conditions = {}
    for brand in brands:
        brand_name = brand.brand.strip()
        if brand_name not in brand_conditions:
            brand_conditions[brand_name] = {
                "category": brand.category,
                "condition": brand.condition or "Authorization required",
                "status": brand.status
            }
        else:
            # Update condition if this one is more specific
            if brand.condition:
                brand_conditions[brand_name]["condition"] = brand.condition
    
    return brand_conditions


def handle_special_question(db: Session, question: str):
    """Handle special question patterns with custom responses."""
    q_lower = question.lower().strip()
    
    # Pattern: "What brands require authorization?"
    # Match various phrasings like "what brands require authorization?", "Which brands need authorization?", etc.
    has_brand_keyword = any(phrase in q_lower for phrase in ["what brand", "which brand", "brands require", "brand require", "brands need", "brand need"])
    has_auth_keyword = any(phrase in q_lower for phrase in ["authorization", "authorisation", "authorized", "authorised"])
    
    if has_brand_keyword and has_auth_keyword:
        brands = get_authorized_brands_list(db)
        if brands:
            brand_list = "\n".join([f"• {name} - {info['condition']}" for name, info in list(brands.items())[:20]])
            return {
                "decision": "Info",
                "reason": f"Found {len(brands)} brands with authorization requirements",
                "answer": f"The following brands require authorization to sell:\n\n{brand_list}\n\nFor complete authorization requirements, please contact our seller support team."
            }
        else:
            return {
                "decision": "Info",
                "reason": "No restricted brands found",
                "answer": "No brands with authorization requirements are currently registered in the system."
            }
    
    # Pattern: "can i sell fake products?" or similar
    if "fake" in q_lower or "counterfeit" in q_lower or "replica" in q_lower:
        # Check and add "fake" to blacklist if not present
        was_added = check_and_add_blacklisted_keyword(db, "fake")
        
        if was_added:
            return {
                "decision": "Blocked",
                "reason": "Keyword 'fake' was not in blacklist - added automatically",
                "answer": "This term is not allowed. The keyword 'fake' has been added to the prohibited list. Please do not list counterfeit or fake products as this violates our platform policies."
            }
        else:
            return {
                "decision": "Blocked",
                "reason": "Contains prohibited keyword 'fake'",
                "answer": "This term is not allowed. Selling fake or counterfeit products is strictly prohibited on our platform. This includes replicas, knockoffs, and any items falsely representing brand identity."
            }
    
    # Pattern: "can i list used electronics?" or "can i sell used products?"
    if ("used" in q_lower or "secondhand" in q_lower or "refurbished" in q_lower):
        # Check if "used" is in prohibited products or blacklisted keywords
        used_prohibited = db.query(ProhibitedProduct).filter(
            ProhibitedProduct.keyword == "used"
        ).first()
        
        if not used_prohibited:
            # Add "used" to prohibited products
            new_product = ProhibitedProduct(
                keyword="used",
                category="product_condition",
                country=None,
                status="prohibited",
                notes="Only new products allowed"
            )
            db.add(new_product)
            db.commit()
        
        return {
            "decision": "Blocked",
            "reason": "Used products are not allowed",
            "answer": "Only New Products are allowed to be sold. Used, secondhand, or refurbished items cannot be listed on our platform."
        }
    
    return None  # Not a special question


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
    
    # Check for special question patterns first
    special_result = handle_special_question(db, q.question)
    if special_result:
        # Save to chat history
        chat = ChatHistory(
            session_id=q.session_id,
            question=q.question,
            decision=special_result["decision"],
            reason=special_result["reason"]
        )
        db.add(chat)
        db.commit()
        
        return ChatResponse(
            decision=special_result["decision"],
            reason=special_result["reason"],
            answer=special_result["answer"],
            entities=entities
        )
    
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


@app.post("/ask/guest", response_model=ChatResponse)
async def ask_compliance_question_guest(
    q: ChatRequest
):
    """Guest endpoint for compliance questions - no authentication required."""
    global request_count, request_times
    start_time = time.time()
    request_count += 1
    
    # Create a new session for guest
    session_id = q.session_id or f"guest_{int(time.time())}"
    
    # Get session memory
    memory = get_memory(session_id)
    
    # Extract entities from question
    entities = extract_entities(q.question)
    
    # Apply memory context if available
    category = entities.get("category") or memory.get("category")
    country = entities.get("country") or memory.get("country")
    
    # Update memory
    update_memory(session_id, {
        "brand": entities.get("brand"),
        "category": category,
        "country": country
    })
    
    # Get database session
    from .core.database import SessionLocal
    db = SessionLocal()
    
    try:
        # Check for special question patterns first
        special_result = handle_special_question(db, q.question)
        if special_result:
            return ChatResponse(
                decision=special_result["decision"],
                reason=special_result["reason"],
                answer=special_result["answer"],
                entities=entities
            )
        
        # Run compliance check
        policy_engine = PolicyEngine(db)
        result = policy_engine.check_compliance(
            q.question, 
            country=country, 
            category=category
        )
        
        # Generate LLM explanation with error handling
        try:
            answer = generate_explanation(
                question=q.question,
                decision=result["decision"],
                reason=result["reason"],
                role="guest",
                detected_entities=entities
            )
        except Exception as llm_error:
            # If LLM fails, use the policy engine result directly
            print(f"LLM service error for guest: {llm_error}")
            answer = result["reason"]
        
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
    except Exception as e:
        print(f"Guest endpoint error: {e}")
        # Return a safe fallback response
        return ChatResponse(
            decision="Allowed",
            reason="Could not process question",
            answer="I apologize, but I encountered an issue processing your request. Please try again or rephrase your question.",
            entities=entities
        )
    finally:
        db.close()

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
    """Upload and process policy file (Excel, PDF, or DOCX)."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Determine file type from filename or content type
    filename = file.filename.lower()
    
    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        suffix = ".xlsx"
    elif filename.endswith('.pdf'):
        suffix = ".pdf"
    elif filename.endswith('.docx') or filename.endswith('.doc'):
        suffix = ".docx"
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .xlsx, .pdf, or .docx files")
    
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Process the file based on type
        policy_engine = PolicyEngine(db)
        
        if suffix == '.xlsx':
            results = policy_engine.rebuild_from_excel(tmp_path)
        elif suffix == '.pdf':
            # For PDF files, extract text and create a simple format
            results = process_pdf_policy(tmp_path, policy_engine, db)
        else:
            # For DOCX files
            results = process_docx_policy(tmp_path, policy_engine, db)
        
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


def process_pdf_policy(filepath: str, policy_engine: PolicyEngine, db: Session):
    """Extract text from PDF and create policy entries."""
    try:
        from pypdf import PdfReader
        
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # Parse the extracted text (simple keyword extraction)
        return parse_text_to_policies(text, policy_engine, db)
    except Exception as e:
        raise Exception(f"Failed to process PDF: {e}")


def process_docx_policy(filepath: str, policy_engine: PolicyEngine, db: Session):
    """Extract text from DOCX and create policy entries."""
    try:
        from docx import Document
        
        doc = Document(filepath)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        # Parse the extracted text
        return parse_text_to_policies(text, policy_engine, db)
    except Exception as e:
        raise Exception(f"Failed to process DOCX: {e}")


def parse_text_to_policies(text: str, policy_engine: PolicyEngine, db: Session):
    """Parse extracted text into policy entries."""
    from ..models import BlacklistedKeyword, RestrictedBrand, ProhibitedProduct
    
    results = {"keywords": 0, "brands": 0, "products": 0}
    
    # Simple parsing - look for keywords, brands, products
    keywords = []
    brands = []
    products = []
    
    lines = text.lower().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Simple heuristics for classification
        if any(word in line for word in ['fake', 'counterfeit', 'replica', 'knockoff', 'illegal', 'prohibited']):
            if line not in keywords:
                keywords.append(line[:100])  # Truncate if too long
                results["keywords"] += 1
        
        if any(word in line for word in ['brand', 'nike', 'adidas', 'gucci', 'apple', 'samsung']):
            if line not in brands:
                brands.append(line[:100])
                results["brands"] += 1
        
        if any(word in line for word in ['product', 'drug', 'weapon', 'alcohol', 'tobacco']):
            if line not in products:
                products.append(line[:100])
                results["products"] += 1
    
    # Add to database
    for kw_text in keywords:
        kw = BlacklistedKeyword(
            keyword=kw_text,
            severity="high",
            scope="global",
            description=f"Extracted from uploaded policy document"
        )
        db.add(kw)
    
    for brand_text in brands:
        brand = RestrictedBrand(
            brand=brand_text,
            status="restricted",
            condition="Authorization required"
        )
        db.add(brand)
    
    for product_text in products:
        product = ProhibitedProduct(
            keyword=product_text,
            status="prohibited",
            notes="Extracted from uploaded policy document"
        )
        db.add(product)
    
    db.commit()
    
    return results

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
# User Management Endpoints
# ============================================

@app.get("/admin/users", response_model=list[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all users with pagination."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@app.post("/admin/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new user."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if username already exists
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Validate role
    if user_data.role not in ["admin", "seller", "legal"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be admin, seller, or legal")
    
    user = User(
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log the action
    log = SystemLog(
        level="info",
        category="admin",
        message=f"Created new user: {user_data.username} with role: {user_data.role}",
        user_id=current_user.id,
        extra_data=json.dumps({"action": "create_user", "target_user": user_data.username})
    )
    db.add(log)
    db.commit()
    
    return user

@app.put("/admin/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing user."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent modifying the last admin
    if user.role == "admin" and user.id == current_user.id:
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot modify the last admin account")
    
    # Update fields if provided
    if user_data.username is not None:
        # Check if new username is taken
        existing = db.query(User).filter(User.username == user_data.username, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        user.username = user_data.username
    
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    
    if user_data.role is not None:
        if user_data.role not in ["admin", "seller", "legal"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be admin, seller, or legal")
        user.role = user_data.role
    
    db.commit()
    db.refresh(user)
    
    # Log the action
    log = SystemLog(
        level="info",
        category="admin",
        message=f"Updated user: {user.username} (ID: {user_id})",
        user_id=current_user.id,
        extra_data=json.dumps({"action": "update_user", "user_id": user_id, "updates": user_data.model_dump(exclude_none=True)})
    )
    db.add(log)
    db.commit()
    
    return user

@app.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Prevent deleting the last admin
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin account")
    
    username = user.username
    db.delete(user)
    db.commit()
    
    # Log the action
    log = SystemLog(
        level="warning",
        category="admin",
        message=f"Deleted user: {username} (ID: {user_id})",
        user_id=current_user.id,
        extra_data=json.dumps({"action": "delete_user", "user_id": user_id, "deleted_username": username})
    )
    db.add(log)
    db.commit()
    
    return {"status": "success", "message": f"User {username} deleted successfully"}


# ============================================
# Logs Endpoints
# ============================================

@app.get("/admin/logs", response_model=list[LogResponse])
async def get_logs(
    level: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get system logs with filtering and pagination."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = db.query(SystemLog)
    
    # Apply filters
    if level:
        query = query.filter(SystemLog.level == level)
    if category:
        query = query.filter(SystemLog.category == category)
    if start_date:
        query = query.filter(SystemLog.created_at >= start_date)
    if end_date:
        query = query.filter(SystemLog.created_at <= end_date)
    
    # Order by created_at descending and apply pagination
    logs = query.order_by(SystemLog.created_at.desc()).offset(offset).limit(limit).all()
    
    return logs

@app.get("/admin/logs/stats")
async def get_log_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get log statistics."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from sqlalchemy import func
    
    # Count by level
    level_counts = dict(
        db.query(SystemLog.level, func.count(SystemLog.id))
        .group_by(SystemLog.level)
        .all()
    )
    
    # Count by category
    category_counts = dict(
        db.query(SystemLog.category, func.count(SystemLog.id))
        .group_by(SystemLog.category)
        .all()
    )
    
    # Total count
    total = db.query(SystemLog).count()
    
    # Recent errors (last 24 hours)
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_errors = db.query(SystemLog).filter(
        SystemLog.level == "error",
        SystemLog.created_at >= yesterday
    ).count()
    
    return {
        "total": total,
        "by_level": level_counts,
        "by_category": category_counts,
        "recent_errors_24h": recent_errors
    }

@app.post("/admin/logs")
async def create_log(
    log_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new log entry (for internal use)."""
    if current_user.role not in ["admin", "legal"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    log = SystemLog(
        level=log_data.get("level", "info"),
        category=log_data.get("category", "system"),
        message=log_data.get("message", ""),
        user_id=current_user.id,
        ip_address=log_data.get("ip_address"),
        extra_data=json.dumps(log_data.get("extra_data")) if log_data.get("extra_data") else None
    )
    db.add(log)
    db.commit()
    
    return {"status": "success", "log_id": log.id}


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
    from .services.llm_service import gpt4all_manager, cloud_client, load_manager
    
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

# ============================================
# Debug & Admin Reset Endpoints
# ============================================

@app.get("/debug/users")
async def debug_users(db: Session = Depends(get_db)):
    """Debug endpoint to list all users and check authentication."""
    from .services.auth_service import get_password_hash, verify_password
    
    users = db.query(User).all()
    result = []
    
    for user in users:
        # Test password for admin and seller
        test_password = "admin123" if user.username == "admin" else "seller123"
        can_verify = verify_password(test_password, user.password_hash)
        
        result.append({
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "password_hash": user.password_hash[:20] + "...",  # Truncated for security
            "password_matches": can_verify
        })
    
    return {
        "users": result,
        "total": len(users),
        "note": "If password_matches is false, visit /admin/reset-users to reset passwords"
    }

@app.post("/admin/reset-users")
async def reset_users(db: Session = Depends(get_db)):
    """POST endpoint to reset/Create default admin and seller users."""
    from .services.auth_service import get_password_hash
    
    result = {"created": [], "updated": []}
    
    # Create or update admin
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        admin.password_hash = get_password_hash("admin123")
        admin.role = "admin"
        result["updated"].append("admin")
    else:
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin)
        result["created"].append("admin")
    
    # Create or update seller
    seller = db.query(User).filter(User.username == "seller").first()
    if seller:
        seller.password_hash = get_password_hash("seller123")
        seller.role = "seller"
        result["updated"].append("seller")
    else:
        seller = User(
            username="seller",
            password_hash=get_password_hash("seller123"),
            role="seller"
        )
        db.add(seller)
        result["created"].append("seller")
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Default users reset successfully",
        "credentials": {
            "admin": {"username": "admin", "password": "admin123", "role": "admin"},
            "seller": {"username": "seller", "password": "seller123", "role": "seller"}
        },
        "result": result
    }

# Also create a GET version for browser access
@app.get("/admin/reset-users")
async def reset_users_get(db: Session = Depends(get_db)):
    """GET endpoint to reset/Create default admin and seller users."""
    return await reset_users(db)

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
