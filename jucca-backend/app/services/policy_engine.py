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


def calculate_match_score(question: str, keyword: str) -> float:
    """
    Calculate how well a keyword matches a question.
    Returns a score between 0 and 100.
    Only returns high scores for exact or very close matches.
    """
    question_lower = question.lower().strip()
    keyword_lower = keyword.lower().strip()
    
    # Exact word match (case insensitive)
    if keyword_lower == question_lower:
        return 100.0
    
    # Check if keyword is contained in question as a distinct word
    question_words = question_lower.split()
    
    # Check for exact word match
    for word in question_words:
        if word == keyword_lower:
            return 100.0
    
    # Check if keyword (multi-word) appears as phrase in question
    if keyword_lower in question_lower:
        # Check if it's a word-boundary match
        import re
        pattern = r'\b' + re.escape(keyword_lower) + r'\b'
        if re.search(pattern, question_lower):
            return 95.0
    
    # For single-word keywords, only accept exact matches or very high fuzzy scores
    # Increase threshold to 85 to reduce false positives
    if len(keyword_lower.split()) == 1:
        # Very high threshold for single word matching - minimum 85% match
        if fuzz.ratio(keyword_lower, question_lower) >= 85:
            return 80.0
        return 0.0
    
    # For multi-word keywords, require high partial ratio
    score = fuzz.partial_ratio(keyword_lower, question_lower)
    return score if score >= 85 else 0.0


# Common English words to exclude from matching (prepositions, articles, etc.)
COMMON_WORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'between', 'under', 'again', 'further', 'then', 'once',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'must', 'can', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
    'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'this',
    'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'where', 'when',
    'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
    'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
    'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
    'while', 'there', 'here', 'any', 'also', 'now', 'even', 'still', 'well',
    'back', 'out', 'off', 'over', 'get', 'got', 'getting', 'sell', 'selling',
    'sellin', 'could', 'would', 'please', 'thanks', 'thank', 'question', 'ask',
    'want', 'need', 'like', 'know', 'think', 'see', 'look', 'make', 'give',
    'take', 'put', 'come', 'go', 'let', 'say', 'tell', 'ask', 'try', 'call',
    'keep', 'let', 'put', 'seem', 'help', 'show', 'hear', 'play', 'run', 'move',
    'live', 'believe', 'bring', 'happen', 'write', 'provide', 'sit', 'stand',
    'lose', 'pay', 'meet', 'include', 'continue', 'set', 'learn', 'change',
    'lead', 'understand', 'watch', 'follow', 'stop', 'create', 'speak', 'read',
    'allow', 'add', 'spend', 'grow', 'open', 'walk', 'win', 'offer', 'remember',
    'consider', 'appear', 'buy', 'wait', 'serve', 'die', 'send', 'expect', 'build',
    'stay', 'fall', 'cut', 'reach', 'kill', 'remain', 'reach', 'agree', 'add',
    'sell', 'sold', 'buy', 'bought', 'item', 'items', 'product', 'products',
    'nigeria', 'kenya', 'egypt', 'ghana', 'uganda', 'tunisia', 'senegal', 
    'algeria', 'morocco', 'ic', 'ng', 'ke', 'eg', 'dz', 'sn', 'tn', 'ug', 'gh'
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
        keyword_issues, detected_keywords = self._check_blacklisted_keywords(q)
        
        # 2. Check prohibited products (only if question is product-related)
        product_issues = self._check_prohibited_products(q, country, category)
        if product_issues:
            findings["issues"].extend(product_issues)
            findings["decision"] = "Prohibited"
        
        # 3. Check restricted brands (only if question is brand-related)
        brand_issues, detected_brands = self._check_restricted_brands(q, country)
        if brand_issues:
            findings["issues"].extend(brand_issues)
            findings["detected_brands"] = detected_brands
            
            # Check if any brand is FORBIDDEN
            has_forbidden = any("is FORBIDDEN" in issue for issue in brand_issues)
            
            if has_forbidden:
                findings["decision"] = "Blocked"
            # For non-forbidden brands, decision stays as "Allowed" (don't change to "Restricted")
        
        # 4. Process keyword issues - these should block the request
        if keyword_issues:
            findings["issues"].extend(keyword_issues)
            findings["detected_keywords"] = detected_keywords
            
            # Blacklisted keywords should block the request
            has_prohibited = any("prohibited keyword" in issue for issue in keyword_issues)
            has_restricted = any("restricted keyword" in issue for issue in keyword_issues)
            
            if has_prohibited and findings["decision"] == "Allowed":
                findings["decision"] = "Blocked"
            elif has_restricted and findings["decision"] == "Allowed":
                findings["decision"] = "Blocked"
        
        # Generate final reason
        findings["reason"] = self._generate_reason(findings)
        
        return findings
    
    def _check_blacklisted_keywords(self, question: str):
        """Check for blacklisted keywords in the question."""
        keywords = self.db.query(BlacklistedKeyword).all()
        issues = []
        detected = []
        
        # Tokenize question into words for better matching
        question_lower = question.lower()
        question_words = set(question_lower.split())
        question_meaningful = question_words - COMMON_WORDS
        
        for kw in keywords:
            kw_lower = kw.keyword.lower()
            kw_words = set(kw_lower.split())
            
            # Skip keywords that consist mostly of common words
            # A keyword must have at least one meaningful (non-common) word
            kw_meaningful = kw_words - COMMON_WORDS
            if not kw_meaningful:
                continue
            
            # Skip very short keywords (less than 3 chars) to avoid false positives
            if len(kw_lower) < 3:
                continue
            
            # Skip keywords that are just numbers or single characters
            if kw_lower.replace(' ', '').isdigit():
                continue
            
            # Check if meaningful keyword words are in question words
            if kw_meaningful & question_meaningful:
                # At least one meaningful word matches
                detected.append(kw.keyword)
                if kw.severity == "high":
                    issues.append(f"Contains prohibited keyword '{kw.keyword}'")
                else:
                    issues.append(f"Contains restricted keyword '{kw.keyword}'")
            elif len(kw_lower) >= 5:
                # For longer keywords, check for word-boundary matches
                import re
                pattern = r'\b' + re.escape(kw_lower) + r'\b'
                if re.search(pattern, question_lower):
                    detected.append(kw.keyword)
                    if kw.severity == "high":
                        issues.append(f"Contains prohibited keyword '{kw.keyword}'")
                    else:
                        issues.append(f"Contains restricted keyword '{kw.keyword}'")
                # Only use fuzzy matching for very high similarity (95%+)
                elif len(kw_lower) >= 5 and fuzz.ratio(kw_lower, question_lower) >= 95:
                    detected.append(kw.keyword)
                    if kw.severity == "high":
                        issues.append(f"Contains prohibited keyword '{kw.keyword}'")
                    else:
                        issues.append(f"Contains restricted keyword '{kw.keyword}'")
        
        return issues, detected
    
    def _check_prohibited_products(self, question: str, country: str = None, category: str = None):
        """Check if the product is prohibited - only matches when question is about a specific product."""
        products = self.db.query(ProhibitedProduct).all()
        issues = []
        detected = []
        
        # Build a mapping of products by keyword for efficient lookup
        product_map = {}
        for product in products:
            key = product.keyword.lower()
            if key not in product_map:
                product_map[key] = []
            product_map[key].append(product)
        
        # Calculate match scores for all products
        scored_matches = []
        for product in products:
            score = calculate_match_score(question, product.keyword)
            
            # Country filter
            if product.country and country:
                if product.country.lower() != country.lower():
                    score -= 30  # Penalty for wrong country
            
            # Category filter
            if category and product.category:
                if category.lower() not in product.category.lower():
                    score -= 20  # Penalty for wrong category
            
            if score >= 50:  # Threshold for considering a match
                scored_matches.append((score, product))
        
        # Sort by score descending and take top matches
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        
        # Only take products with high enough scores
        seen_keywords = set()
        for score, product in scored_matches:
            # Skip if we've already processed this keyword
            if product.keyword.lower() in seen_keywords:
                continue
            
            # Only process if score is high enough
            if score < 60:
                continue
            
            # Check country restriction
            if product.country and country:
                if product.country.lower() != country.lower():
                    continue
            
            seen_keywords.add(product.keyword.lower())
            detected.append(product.keyword)
            
            # Build the issue message
            country_info = f" in {product.country}" if product.country else ""
            status_info = product.status or "prohibited"
            notes_info = f" - {product.notes}" if product.notes else ""
            issues.append(f"Product '{product.keyword}' is {status_info}{country_info}{notes_info}")
        
        return issues
    
    def _check_restricted_brands(self, question: str, country: str = None):
        """
        Check if any restricted brands are mentioned in the question.
        Only matches when brand name (or alias) appears explicitly in the question.
        """
        brands = self.db.query(RestrictedBrand).all()
        issues = []
        detected = []
        
        # Build a mapping of brand names to their records
        brand_map = {}
        for brand in brands:
            brand_lower = brand.brand.lower()
            if brand_lower not in brand_map:
                brand_map[brand_lower] = []
            brand_map[brand_lower].append(brand)
        
        # Check each brand against the question
        matched_brands = []
        
        for brand_lower, brand_list in brand_map.items():
            brand = brand_list[0]  # Use first record for matching
            
            # Check if brand name appears in question
            score = calculate_match_score(question, brand.brand)
            
            # Also check aliases if available
            max_score = score
            
            # Get question words
            question_lower = question.lower()
            question_words = set(question_lower.split())
            
            # Check for exact word matches
            brand_words = set(brand_lower.split())
            
            # Direct word match
            if brand_words & question_words:
                max_score = max(max_score, 90.0)
            
            # Check if any question word starts with the brand name
            for q_word in question_words:
                if q_word.startswith(brand_lower[:4]) and len(brand_lower) >= 4:
                    # Potential match - check more carefully
                    if fuzz.ratio(q_word, brand_lower) >= 75:
                        max_score = max(max_score, 70.0)
            
            # Only consider as match if score is high enough
            if max_score >= 75:
                matched_brands.append((max_score, brand))
        
        # Sort by score descending
        matched_brands.sort(key=lambda x: x[0], reverse=True)
        
        # Process matches
        seen_brands = set()
        for score, brand in matched_brands:
            brand_key = brand.brand.lower()
            
            # Skip if we've already processed this brand
            if brand_key in seen_brands:
                continue
            
            # Final threshold check
            if score < 75:
                continue
            
            # Skip very short brand names that might match too broadly
            if len(brand.brand) < 3:
                continue
            
            seen_brands.add(brand_key)
            detected.append(brand.brand)
            
            # Build the issue message with proper status
            status = brand.status or "restricted"
            condition = brand.condition or "Authorization required"
            
            # Format status and condition for display
            if status == "forbidden":
                status_display = "Blocked"
                condition_formatted = f"Note: {condition}"
            elif status == "allowed_with_qc_for_fakes":
                status_display = "Allowed"
                # Ensure condition clearly states QC requirement
                if "ALLOWED WITH QC FOR FAKES" not in condition:
                    condition_formatted = f"Allowed with QC for Fakes. {condition}"
                else:
                    condition_formatted = condition
            else:
                # For 'allowed' or 'restricted' status
                status_display = "Allowed"
                if "Allowed in all categories" in condition:
                    condition_formatted = condition
                elif "allowed with QC" in condition.lower() or "allowed with qc" in condition.lower():
                    condition_formatted = condition
                else:
                    condition_formatted = f"Allowed. {condition}"
            
            issues.append(f"Brand '{brand.brand}' is {status_display}. {condition_formatted}")
        
        return issues, detected
    
    def _generate_reason(self, findings: dict) -> str:
        """Generate a human-readable reason for the decision."""
        # Separate brand issues from keyword issues for cleaner output
        brand_issues = [issue for issue in findings["issues"] if "Brand '" in issue]
        product_issues = [issue for issue in findings["issues"] if "Product '" in issue]
        keyword_issues = [issue for issue in findings["issues"] if "Contains" in issue]
        
        # Prioritize brand and product issues over generic keyword matches
        important_issues = brand_issues + product_issues
        
        if not findings["issues"] or (not important_issues and not keyword_issues):
            # No issues at all
            return "No policy violations found. This listing appears to be compliant."
        
        if important_issues:
            # There are brand or product restrictions
            main_issue = important_issues[0]
            
            # Check if there are additional keyword issues
            remaining_keywords = len(keyword_issues)
            
            if remaining_keywords > 0:
                return f"{main_issue} Note: Some related terms ({remaining_keywords} keyword(s)) were detected in your question."
            else:
                return main_issue
        else:
            # Only keyword issues - these are typically spam patterns or brand mentions
            # Extract unique keywords
            unique_keywords = set()
            for issue in keyword_issues:
                import re
                match = re.search(r"'([^']+)'", issue)
                if match:
                    unique_keywords.add(match.group(1))
            
            # Check if detected keywords are brand names (restricted brands mentioned)
            brand_keywords = []
            other_keywords = []
            for kw in unique_keywords:
                # Check if keyword looks like a brand name (contains specific brand terms)
                if any(brand_term in kw.lower() for brand_term in ['shoe', 'shoes', 'dress', 'bag', 'watch', 'perfume', 'cream', 'oil']):
                    # This might be a product type, not a brand violation
                    other_keywords.append(kw)
                else:
                    brand_keywords.append(kw)
            
            # If only general product terms are found, give positive response
            if not brand_keywords:
                keyword_info = ""
                if other_keywords:
                    if len(other_keywords) == 1:
                        keyword_info = f" Note: Some related terms like '{list(other_keywords)[0]}' were detected."
                    else:
                        keywords_list = ", ".join(sorted(other_keywords)[:3])
                        keyword_info = f" Note: Some related terms like {keywords_list} were detected."
                
                return f"No brand restrictions found for general product listings.{keyword_info} Please ensure your specific product complies with all platform policies."
            else:
                # There are actual restricted brand keywords
                if len(brand_keywords) == 1:
                    return f"Contains restricted keyword '{list(brand_keywords)[0]}'."
                else:
                    keywords_list = ", ".join(sorted(brand_keywords)[:5])
                    remaining = len(brand_keywords) - 5
                    if remaining > 0:
                        return f"Contains restricted keywords: {keywords_list} (+ {remaining} more)."
                    else:
                        return f"Contains restricted keywords: {keywords_list}."
    
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
