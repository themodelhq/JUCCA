#!/usr/bin/env python3
"""Initialize the JUCCA database with default policy data."""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.core.database import engine, Base, SessionLocal
from app.models import User, BlacklistedKeyword, RestrictedBrand, ProhibitedProduct, SystemLog
from app.services.auth_service import get_password_hash

# Create tables
Base.metadata.create_all(bind=engine)

def seed_database():
    """Seed database with default data."""
    db = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(User).first():
            print("Database already seeded. Skipping...")
            return
        
        # Create default admin user
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin)
        
        # Create demo seller
        seller = User(
            username="seller",
            password_hash=get_password_hash("seller123"),
            role="seller"
        )
        db.add(seller)
        
        # Seed blacklisted keywords
        blacklist_keywords = [
            ("fake", "high", "global", "Counterfeit/fake products"),
            ("counterfeit", "high", "global", "Counterfeit items"),
            ("replica", "high", "global", "Replica products"),
            ("knockoff", "high", "global", "Knockoff products"),
            ("clone", "high", "global", "Cloned products"),
            ("dupe", "medium", "global", "Dupes and copies"),
            ("illegal", "high", "global", "Illegal products"),
            ("stolen", "high", "global", "Stolen goods"),
            ("drugs", "high", "global", "Prohibited substances"),
            ("weapon", "high", "global", "Weapons and firearms"),
            ("porn", "high", "global", "Adult content"),
            ("tobacco", "medium", "global", "Tobacco products"),
        ]
        
        for kw, sev, scope, desc in blacklist_keywords:
            keyword = BlacklistedKeyword(
                keyword=kw,
                severity=sev,
                scope=scope,
                description=desc
            )
            db.add(keyword)
        
        # Seed restricted brands
        restricted_brands = [
            ("Nike", "Fashion", None, "restricted", "Only authorized resellers can list Nike products. Proof of authorization required."),
            ("Adidas", "Fashion", None, "restricted", "Only authorized resellers can list Adidas products. Authorization document required."),
            ("Apple", "Electronics", None, "restricted", "Apple products require proof of purchase and can only be sold by authorized resellers."),
            ("Samsung", "Electronics", None, "restricted", "Samsung products require warranty verification."),
            ("Gucci", "Fashion", None, "restricted", "Gucci products require authentication certificate."),
            ("Louis Vuitton", "Fashion", None, "restricted", "LV products require authentication certificate."),
            ("Chanel", "Fashion", None, "restricted", "Chanel products require authentication certificate."),
            ("Rolex", "Fashion", None, "restricted", "Rolex watches require authentication certificate."),
            ("Omega", "Fashion", None, "restricted", "Omega watches require authentication certificate."),
            ("Huawei", "Electronics", None, "restricted", "Huawei products require warranty verification."),
        ]
        
        for brand, cat, country, status, condition in restricted_brands:
            rb = RestrictedBrand(
                brand=brand,
                category=cat,
                country=country,
                status=status,
                condition=condition
            )
            db.add(rb)
        
        # Seed prohibited products
        prohibited_products = [
            ("weapons", "General", None, "prohibited", "Firearms, knives, and other weapons are prohibited"),
            ("explosives", "General", None, "prohibited", "Fireworks and explosive materials"),
            ("drugs", "Health", None, "prohibited", "Controlled substances and medications without prescription"),
            ("prescription drugs", "Health", None, "prohibited", "Prescription medications require proper licensing"),
            ("counterfeit currency", "General", None, "prohibited", "Fake money and documents"),
            ("wildlife products", "General", None, "prohibited", "Endangered species products"),
            ("human organs", "General", None, "prohibited", "Prohibited by law"),
            ("alcohol", "Food & Bev", None, "prohibited", "Alcohol sales restricted by local laws"),
            ("tobacco products", "Health", None, "prohibited", "Tobacco products sales restrictions apply"),
            ("blood", "Health", None, "prohibited", "Body fluids prohibited"),
            ("knives", "General", None, "prohibited", "Certain types of knives are prohibited"),
        ]
        
        for keyword, cat, country, status, notes in prohibited_products:
            pp = ProhibitedProduct(
                keyword=keyword,
                category=cat,
                country=country,
                status=status,
                notes=notes
            )
            db.add(pp)
        
        db.commit()
        print("Database seeded successfully!")
        print("\nDefault users:")
        print("  Admin: admin / admin123")
        print("  Seller: seller / seller123")
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
