#!/usr/bin/env python3
"""Reload all policy data from JSON file - clears existing data first."""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models import User, BlacklistedKeyword, RestrictedBrand, ProhibitedProduct, ChatHistory, SystemLog
from app.services.auth_service import get_password_hash

def clear_and_reload_policies():
    """Clear all policy data and reload from JSON file."""
    db = SessionLocal()
    
    try:
        print("Clearing existing policy data...")
        
        # Clear in reverse order of dependencies
        db.query(SystemLog).delete()
        db.query(ChatHistory).delete()
        db.query(BlacklistedKeyword).delete()
        db.query(RestrictedBrand).delete()
        db.query(ProhibitedProduct).delete()
        
        db.commit()
        print("✓ Cleared all policy data")
        
        # Load policy data from JSON file
        import json
        from pathlib import Path
        
        policy_file = Path(__file__).parent.parent / "data" / "policy_data.json"
        if not policy_file.exists():
            print("✗ Policy data file not found")
            return
            
        with open(policy_file, 'r') as f:
            policy_data = json.load(f)
        
        print("\nLoading policy data...")
        
        keywords_count = 0
        brands_count = 0
        products_count = 0
        
        # Parse new comprehensive format
        blacklisted_keywords = policy_data.get("blacklisted_keywords", {})
        restricted_brands = policy_data.get("restricted_brands", {})
        prohibited_products = policy_data.get("prohibited_products", {})
        
        # Handle new format with country-specific keywords
        if isinstance(blacklisted_keywords, dict):
            for keyword, keyword_data in blacklisted_keywords.items():
                if isinstance(keyword_data, dict):
                    target_type = keyword_data.get("target_type", "international")
                    status = keyword_data.get("status", "enabled")
                    countries = keyword_data.get("countries", [])
                    
                    keyword = BlacklistedKeyword(
                        keyword=keyword.strip().lower(),
                        severity="high" if status == "enabled" else "medium",
                        scope=",".join(countries) if countries else "global",
                        description=f"Blacklisted keyword - target_type: {target_type}, status: {status}"
                    )
                    db.add(keyword)
                    keywords_count += 1
        
        # Handle new format with nested brand categories
        if isinstance(restricted_brands, dict):
            for category_key, category_data in restricted_brands.items():
                if isinstance(category_data, dict):
                    description = category_data.get("description", "")
                    
                    brands_data = category_data.get("brands", {})
                    if isinstance(brands_data, dict):
                        for brand_name, brand_info in brands_data.items():
                            if isinstance(brand_info, dict):
                                restriction_type = brand_info.get("restriction_type", "restricted")
                                note = brand_info.get("note", description)
                                countries = brand_info.get("countries", [])
                                exceptions = brand_info.get("exceptions", {})
                                
                                # Format condition based on restriction type
                                if restriction_type == "FORBIDDEN":
                                    condition = "This brand is FORBIDDEN across all categories in all countries"
                                elif restriction_type == "ALLOWED WITH QC FOR FAKES":
                                    countries_str = ", ".join(countries) if countries else "selected countries"
                                    condition = f"Allowed with QC for fakes verification in {countries_str}"
                                else:
                                    condition = note
                                
                                brand = RestrictedBrand(
                                    brand=brand_name.strip(),
                                    category=category_key,
                                    country=None,
                                    status=restriction_type.lower().replace(" ", "_"),
                                    condition=condition
                                )
                                db.add(brand)
                                brands_count += 1
        
        # Handle new format with nested product rules
        if isinstance(prohibited_products, dict):
            for product_key, product_data in prohibited_products.items():
                if isinstance(product_data, dict):
                    # The structure is {product_name: {country_code: status}}
                    for country, status in product_data.items():
                        if status and str(status).strip() and country not in ['name', 'description']:
                            is_blocked = "blocked" in str(status).lower()
                            
                            product = ProhibitedProduct(
                                keyword=product_key.lower(),
                                category=None,
                                country=country,
                                status="prohibited" if is_blocked else "restricted",
                                notes=f"{status} in {country}"
                            )
                            db.add(product)
                            products_count += 1
        
        db.commit()
        
        print(f"\n✓ Policy data loaded successfully:")
        print(f"  - {keywords_count} blacklisted keywords")
        print(f"  - {brands_count} restricted brands")
        print(f"  - {products_count} prohibited products")
        
        # Recreate default users if needed
        print("\nEnsuring default users exist...")
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            admin.password_hash = get_password_hash("admin123")
            admin.role = "admin"
        else:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin"
            )
            db.add(admin)
        
        seller = db.query(User).filter(User.username == "seller").first()
        if seller:
            seller.password_hash = get_password_hash("seller123")
            seller.role = "seller"
        else:
            seller = User(
                username="seller",
                password_hash=get_password_hash("seller123"),
                role="seller"
            )
            db.add(seller)
        
        db.commit()
        print("✓ Default users verified")
        print("\nDefault credentials:")
        print("  Admin: admin / admin123")
        print("  Seller: seller / seller123")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clear_and_reload_policies()
