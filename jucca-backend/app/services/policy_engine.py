import pandas as pd
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from ..models import BlacklistedKeyword, RestrictedBrand, ProhibitedProduct

# Mapping of common single words to their full phrase equivalents
# This helps match questions like "can i sell drones?" to "Drones or remotely controlled aircraft"
PRODUCT_ALIASES = {
    # Drones and remote controlled items
    "drone": ["drones or remotely controlled aircraft", "drone", "drones", "remotely controlled aircraft", "rc drone", "quadcopter", "uav", "unmanned aerial vehicle"],
    "drones": ["drones or remotely controlled aircraft", "drone", "drones", "remotely controlled aircraft", "rc drone", "quadcopter", "uav", "unmanned aerial vehicle"],
    
    # Weapons
    "gun": ["firearms and weapons", "gun", "guns", "pistol", "rifle", "shotgun", "handgun", "firearm"],
    "guns": ["firearms and weapons", "gun", "guns", "pistol", "rifle", "shotgun", "handgun", "firearm"],
    "weapon": ["firearms and weapons", "weapon", "weapons", "firearm", "firearms"],
    "weapons": ["firearms and weapons", "weapon", "weapons", "firearm", "firearms"],
    
    # Knives
    "knife": ["knives and sharp weapons", "knife", "knives", "sharp objects", "blade", "blades"],
    "knives": ["knives and sharp weapons", "knife", "knives", "sharp objects", "blade", "blades"],
    
    # Night vision
    "night vision": ["night vision devices", "night vision", "nv devices", "night vision goggles"],
    
    #Spy products
    "spy camera": ["spy products", "spy camera", "hidden camera", "nanny cam", "surveillance"],
    "hidden camera": ["spy products", "spy camera", "hidden camera", "nanny cam", "surveillance"],
    
    # Remote controls
    "remote": ["remote controls", "remote control", "remote", "remote controller", "tv remote"],
    
    # Gaming
    "video games": ["cd-电脑游戏", "video games", "computer games", "gaming", "video game", "games"],
    "computer games": ["cd-电脑游戏", "video games", "computer games", "gaming", "video game", "games"],
    
    # Dietary supplements
    "supplements": ["dietary supplements", "supplements", "dietary", "nutrition supplements", "vitamins"],
    "vitamins": ["dietary supplements", "supplements", "dietary", "nutrition supplements", "vitamins"],
    
    # COVID
    "covid": ["covid-19 test kits", "covid test", "coronavirus test", "rapid test", "antigen test"],
    "covid test": ["covid-19 test kits", "covid test", "coronavirus test", "rapid test", "antigen test"],
    
    # Medical equipment
    "dialysis": ["dialysis machines", "dialysis", "kidney machine", "dialysis equipment"],
    "ventilator": ["ventilators", "ventilator", "respirator", "breathing machine"],
    "catheter": ["catheters", "catheter", "urinary catheter", "medical catheter"],
    
    # Radioactive
    "radioactive": ["radioactive products", "放射性产品", "radioactive", "radiation", "nuclear"],
    
    # Toxic
    "toxic": ["有毒物质", "toxic substances", "toxic", "poison", "hazardous materials"],
    
    # Reptile skins
    "reptile skin": ["certain reptile skins", "某些爬行动物的皮肤", "reptile skin", "crocodile skin", "snake skin", "lizard skin"],
    "crocodile skin": ["certain reptile skins", "某些爬行动物的皮肤", "reptile skin", "crocodile skin", "snake skin", "lizard skin"],
    
    # Camouflage
    "camo": ["camouflage clothing / items", "camouflage", "camo", "military pattern", "camouflage clothing"],
    "camouflage": ["camouflage clothing / items", "camouflage", "camo", "military pattern", "camouflage clothing"],
    
    # Adult products
    "adult": ["adult products", "adult", "adult toys", "intimate products"],
    "adult toy": ["adult products", "adult", "adult toys", "intimate products"],
    
    # Nicotine
    "nicotine": ["nicotine products", "nicotine", "vape", "e-cigarette", "e cig"],
    "vape": ["nicotine products", "nicotine", "vape", "e-cigarette", "e cig"],
    "e-cigarette": ["nicotine products", "nicotine", "vape", "e-cigarette", "e cig"],
    
    # Medical devices
    "medical device": ["medical devices", "medical device", "medical equipment", "healthcare device"],
    
    # Tracking devices
    "gps": ["all tracking devices", "gps tracker", "tracking device", "gps", "location tracker"],
    "gps tracker": ["all tracking devices", "gps tracker", "tracking device", "gps", "location tracker"],
    
    # GSM
    "gsm": ["gsm signal booster", "gsm booster", "signal booster", "mobile booster", "cell booster"],
    "signal booster": ["gsm signal booster", "gsm booster", "signal booster", "mobile booster", "cell booster"],
    
    # Camera spectacles
    "smart glasses": ["camera spectacles / smart glasses", "smart glasses", "camera glasses", "recording glasses", "spy glasses"],
    "recording glasses": ["camera spectacles / smart glasses", "smart glasses", "camera glasses", "recording glasses", "spy glasses"],
    
    # Sharp objects
    "sharp": ["sharp objects", "sharp", "sharp items", "pointed objects"],
}

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
            
            # First, check for direct word matches (improved matching)
            product_keyword = product.keyword.lower()
            
            # Check if any word in the question matches a word in the product name
            question_words = set(question.split())
            product_words = set(product_keyword.split())
            
            # Also get expanded aliases for better matching
            expanded_product_terms = set([product_keyword])
            for word in question_words:
                if word in PRODUCT_ALIASES:
                    expanded_product_terms.update(PRODUCT_ALIASES[word])
            
            # Check if any question word is in the product terms or vice versa
            matched = False
            for q_word in question_words:
                for p_term in expanded_product_terms:
                    # Check if the question word is contained in the product term
                    if len(q_word) > 2 and q_word in p_term:
                        matched = True
                        break
                    # Check exact match
                    if q_word == p_term:
                        matched = True
                        break
                    # Use fuzzy matching for the word against the product term
                    if fuzz.partial_ratio(q_word, p_term) > 85:
                        matched = True
                        break
                if matched:
                    break
            
            # If no direct match, try fuzzy matching on the full strings
            if not matched:
                # Use fuzzy matching with lower threshold for multi-word phrases
                if fuzz.partial_ratio(product_keyword, question) > 70:
                    matched = True
            
            if matched:
                detected.append(product.keyword)
                # Get the display name (use notes if available, otherwise the keyword)
                display_name = product.notes or product.keyword
                issues.append(f"Product '{display_name}' is {product.status} ({product.notes or 'No additional info'})")
        
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
