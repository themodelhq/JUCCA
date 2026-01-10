import re

# Country mappings
COUNTRIES = {
    "nigeria": "NG",
    "ghana": "GH",
    "kenya": "KE",
    "egypt": "EG",
    "uganda": "UG",
    "tanzania": "TZ",
    "south africa": "ZA",
    "morocco": "MA",
    "algeria": "DZ",
    "tunisia": "TN",
    "senegal": "SN",
    "ivory coast": "CI",
    "cameroon": "CM"
}

# Category mappings
CATEGORIES = {
    "shoe": "Fashion",
    "shoes": "Fashion",
    "sneaker": "Fashion",
    "sneakers": "Fashion",
    "clothing": "Fashion",
    "clothes": "Fashion",
    "dress": "Fashion",
    "shirt": "Fashion",
    "pants": "Fashion",
    "bag": "Fashion",
    "bags": "Fashion",
    "watch": "Fashion",
    "watches": "Fashion",
    "phone": "Electronics",
    "phones": "Electronics",
    "smartphone": "Electronics",
    "laptop": "Electronics",
    "computer": "Electronics",
    "headphone": "Electronics",
    "earphone": "Electronics",
    "drug": "Health",
    "drugs": "Health",
    "medicine": "Health",
    "medication": "Health",
    "supplement": "Health",
    "cosmetic": "Beauty",
    "cosmetics": "Beauty",
    "makeup": "Beauty",
    "skincare": "Beauty",
    "perfume": "Beauty",
    "fragrance": "Beauty"
}

# Known brands for detection
KNOWN_BRANDS = [
    "nike", "adidas", "puma", "new balance", "under armour",
    "apple", "samsung", "huawei", "xiaomi", "oppo", "vivo",
    "gucci", "prada", "lv", "louis vuitton", "channel", "chanel",
    "rolex", "omega", "hublot", "cartier",
    "cocacola", "coca-cola", "pepsi",
    "colgate", "pampers", "gillette", "dove", "axe", "lux",
    "mac", "maybelline", "loreal", "revlon"
]

def extract_entities(question: str):
    """Extract brand, category, country, and flags from natural language question."""
    q = question.lower().strip()
    
    # Extract country
    country = None
    for country_name, code in COUNTRIES.items():
        if country_name in q:
            country = code
            break
    
    # Extract category
    category = None
    for cat_name, cat_value in CATEGORIES.items():
        if cat_name in q:
            category = cat_value
            break
    
    # Extract brand (check known brands first)
    brand = None
    for known_brand in KNOWN_BRANDS:
        if known_brand in q:
            # Get the proper case version
            brand = known_brand.title()
            break
    
    # Also try capitalized word detection as fallback
    if not brand:
        brand_matches = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", question)
        if brand_matches:
            potential_brand = brand_matches[0]
            # Verify it's not a common word
            if potential_brand.lower() not in ["can", "the", "this", "what", "how", "selling", "sell"]:
                brand = potential_brand
    
    # Detect flags
    flags = {
        "used": "used" in q or "secondhand" in q or "pre-owned" in q,
        "counterfeit": "fake" in q or "counterfeit" in q or "replica" in q or "knockoff" in q,
        "refurbished": "refurbished" in q or "renewed" in q,
        "bulk": "bulk" in q or "wholesale" in q or "wholesaler" in q
    }
    
    return {
        "brand": brand,
        "category": category,
        "country": country,
        "flags": flags
    }
