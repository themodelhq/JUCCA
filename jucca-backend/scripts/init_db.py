#!/usr/bin/env python3
"""Initialize the JUCCA database with comprehensive policy data from JSON file."""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.core.database import engine, Base, SessionLocal
from app.models import User, BlacklistedKeyword, RestrictedBrand, ProhibitedProduct, SystemLog
from app.services.auth_service import get_password_hash


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def seed_database():
    """Seed database with comprehensive policy data from JSON file."""
    db = SessionLocal()

    try:
        # Check if already seeded with policy data
        existing_keywords = db.query(BlacklistedKeyword).count()
        if existing_keywords > 0:
            print("Database already contains policy data. Skipping...")
            return

        print("Loading comprehensive policy data...")

        # Load policy data from JSON file
        policy_file = Path(__file__).parent.parent / "data" / "policy_data.json"

        if not policy_file.exists():
            print("ERROR: Policy data file not found at:", policy_file)
            print("Please ensure policy_data.json exists in the data/ directory")
            return

        with open(policy_file, 'r', encoding='utf-8') as f:
            policy_data = json.load(f)

        # Parse blacklisted keywords
        blacklisted_keywords = policy_data.get("blacklisted_keywords", {})
        keywords_count = 0

        if isinstance(blacklisted_keywords, dict):
            for country, keywords in blacklisted_keywords.items():
                if isinstance(keywords, list):
                    for kw in keywords:
                        keyword = BlacklistedKeyword(
                            keyword=kw.strip().lower(),
                            severity="high",
                            scope=country,
                            description=f"Blacklisted keyword for {country}"
                        )
                        db.add(keyword)
                        keywords_count += 1

        # Parse restricted brands
        restricted_brands = policy_data.get("restricted_brands", {})
        brands_count = 0

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

                                brand = RestrictedBrand(
                                    brand=brand_name.strip(),
                                    category=category_key,
                                    country=None,
                                    status=restriction_type.lower().replace(" ", "_"),
                                    condition=note
                                )
                                db.add(brand)
                                brands_count += 1

                    elif isinstance(brands_data, list):
                        for brand_name in brands_data:
                            if isinstance(brand_name, str):
                                brand = RestrictedBrand(
                                    brand=brand_name.strip(),
                                    category=category_key,
                                    country=None,
                                    status="restricted",
                                    condition=description
                                )
                                db.add(brand)
                                brands_count += 1

        # Parse prohibited products
        prohibited_products = policy_data.get("prohibited_products", {})
        products_count = 0

        if isinstance(prohibited_products, dict):
            for product_key, product_data in prohibited_products.items():
                if isinstance(product_data, dict):
                    product_name = product_key

                    # Get country-specific statuses
                    for country, status in product_data.items():
                        if status and str(status).strip():
                            status_str = str(status).strip()
                            is_blocked = "blocked" in status_str.lower()

                            product = ProhibitedProduct(
                                keyword=product_name.lower(),
                                category=product_key,
                                country=country,
                                status="prohibited" if is_blocked else "restricted",
                                notes=f"{status_str} in {country}"
                            )
                            db.add(product)
                            products_count += 1

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

        db.commit()

        print("=" * 60)
        print("Database initialized successfully!")
        print("=" * 60)
        print(f"\nComprehensive policy data loaded:")
        print(f"  - {keywords_count} blacklisted keywords")
        print(f"  - {brands_count} restricted brands")
        print(f"  - {products_count} prohibited product entries")
        print(f"\nDefault users:")
        print(f"  Admin: admin / admin123")
        print(f"  Seller: seller / seller123")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    seed_database()
