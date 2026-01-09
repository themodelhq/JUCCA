import pandas as pd
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from app.models import BlacklistedKeyword, RestrictedBrand, ProhibitedProduct

class PolicyEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def check_compliance(self, question: str, country: str = None, category: str = None):
        """Main compliance checking function."""
        q = question.lower()
        findings = {
            "decision": "Allowed",
            "reason": "No policy violations found.",
            "issues": [],
            "detected_keywords": [],
            "detected_brands": [],
            "detected_products": []
        }
        
        # 1. Check blacklisted keywords
        keyword_issues = self._check_blacklisted_keywords(q)
        if keyword_issues:
            findings["issues"].extend(keyword_issues)
            findings["decision"] = "Blocked"
        
        # 2. Check prohibited products
        product_issues = self._check_prohibited_products(q, country)
        if product_issues:
            findings["issues"].extend(product_issues)
            if findings["decision"] != "Blocked":
                findings["decision"] = "Prohibited"
        
        # 3. Check restricted brands
        brand_issues, detected_brands = self._check_restricted_brands(q, country)
        if brand_issues:
            findings["issues"].extend(brand_issues)
            findings["detected_brands"] = detected_brands
            if findings["decision"] in ["Allowed", "Prohibited"]:
                findings["decision"] = "Restricted"
        
        # Generate final reason
        findings["reason"] = self._generate_reason(findings)
        
        return findings
    
    def _check_blacklisted_keywords(self, question: str):
        """Check for blacklisted keywords in the question."""
        keywords = self.db.query(BlacklistedKeyword).all()
        issues = []
        detected = []
        
        for kw in keywords:
            # Use fuzzy matching with threshold
            if fuzz.partial_ratio(kw.keyword.lower(), question) > 85:
                detected.append(kw.keyword)
                if kw.severity == "high":
                    issues.append(f"Contains prohibited keyword '{kw.keyword}'")
                else:
                    issues.append(f"Contains restricted keyword '{kw.keyword}'")
        
        return issues
    
    def _check_prohibited_products(self, question: str, country: str = None):
        """Check if the product is prohibited."""
        products = self.db.query(ProhibitedProduct).all()
        issues = []
        detected = []
        
        for product in products:
            # Check country restriction
            if product.country and country:
                if product.country.lower() != country.lower():
                    continue
            
            # Use fuzzy matching
            if fuzz.partial_ratio(product.keyword.lower(), question) > 80:
                detected.append(product.keyword)
                issues.append(f"Product '{product.keyword}' is {product.status} ({product.notes or 'No additional info'})")
        
        return issues
    
    def _check_restricted_brands(self, question: str, country: str = None):
        """Check if any restricted brands are mentioned."""
        brands = self.db.query(RestrictedBrand).all()
        issues = []
        detected = []
        
        for brand in brands:
            # Check country restriction
            if brand.country and country:
                if brand.country.lower() != country.lower():
                    continue
            
            # Exact and fuzzy matching for brand names
            brand_lower = brand.brand.lower()
            if brand_lower in question or fuzz.partial_ratio(brand_lower, question) > 85:
                detected.append(brand.brand)
                condition = brand.condition or "Authorization required"
                issues.append(f"Brand '{brand.brand}' is restricted. {condition}")
        
        return issues, detected
    
    def _generate_reason(self, findings: dict) -> str:
        """Generate a human-readable reason for the decision."""
        if not findings["issues"]:
            return "No policy violations found. This listing appears to be compliant."
        
        if len(findings["issues"]) == 1:
            return findings["issues"][0]
        
        return f"Found {len(findings['issues'])} policy issues: " + "; ".join(findings["issues"])
    
    def rebuild_from_excel(self, filepath: str):
        """Rebuild policy tables from Excel file."""
        excel_file = pd.ExcelFile(filepath)
        results = {}
        
        # Process Blacklisted Words sheet
        if "Blacklisted Words" in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name="Blacklisted Words")
            self.db.query(BlacklistedKeyword).delete()
            for _, row in df.iterrows():
                keyword = BlacklistedKeyword(
                    keyword=str(row.get("Keyword", "")).strip(),
                    severity=str(row.get("Severity", "high")).lower(),
                    scope=str(row.get("Scope", "global")).lower(),
                    description=str(row.get("Description", "")) if pd.notna(row.get("Description")) else None
                )
                self.db.add(keyword)
            results["keywords"] = len(df)
        
        # Process Restricted Brands sheet
        if "Restricted Brands" in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name="Restricted Brands")
            self.db.query(RestrictedBrand).delete()
            for _, row in df.iterrows():
                brand = RestrictedBrand(
                    brand=str(row.get("Brand", "")).strip(),
                    category=str(row.get("Category", "")) if pd.notna(row.get("Category")) else None,
                    country=str(row.get("Country", "")) if pd.notna(row.get("Country")) else None,
                    status=str(row.get("Status", "restricted")).lower(),
                    condition=str(row.get("Condition", "")) if pd.notna(row.get("Condition")) else None
                )
                self.db.add(brand)
            results["brands"] = len(df)
        
        # Process Prohibited Categories sheet
        if "Prohibited Categories" in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name="Prohibited Categories")
            self.db.query(ProhibitedProduct).delete()
            for _, row in df.iterrows():
                product = ProhibitedProduct(
                    keyword=str(row.get("Keyword", "")).strip(),
                    category=str(row.get("Category", "")) if pd.notna(row.get("Category")) else None,
                    country=str(row.get("Country", "")) if pd.notna(row.get("Country")) else None,
                    status=str(row.get("Status", "prohibited")).lower(),
                    notes=str(row.get("Notes", "")) if pd.notna(row.get("Notes")) else None
                )
                self.db.add(product)
            results["products"] = len(df)
        
        self.db.commit()
        return results
