import difflib
from datetime import datetime

def calculate_match_score(search, item):
    """
    Calculates a match score from 0 to 100 between a search query and a database item.
    
    search: dict containing category, title, brand, color, date_lost, location
    item: dict-like object (sqlite3.Row) containing the found item details
    """
    score = 0
    max_score = 0
    
    # 1. Category (Weight: 25)
    max_score += 25
    s_category = search.get('category', '').strip().lower()
    i_category = item['category'].strip().lower()
    if s_category and i_category:
        if s_category == i_category:
            score += 25
        elif s_category in i_category or i_category in s_category:
            score += 15

    # 2. Title / Product Name (Weight: 25)
    max_score += 25
    s_title = search.get('title', '').strip().lower()
    i_title = item['title'].strip().lower()
    if s_title and i_title:
        # Check similarity ratio
        ratio = difflib.SequenceMatcher(None, s_title, i_title).ratio()
        score += ratio * 25
    
    # 3. Brand (Weight: 15)
    max_score += 15
    s_brand = search.get('brand', '').strip().lower()
    i_brand = item['brand'].strip().lower()
    if s_brand and i_brand:
        if s_brand == i_brand:
            score += 15
        elif s_brand in i_brand or i_brand in s_brand:
            score += 10
        else:
            ratio = difflib.SequenceMatcher(None, s_brand, i_brand).ratio()
            score += ratio * 15
            
    # 4. Color (Weight: 15)
    max_score += 15
    s_color = search.get('color', '').strip().lower()
    i_color = item['color'].strip().lower()
    if s_color and i_color:
        if s_color == i_color:
            score += 15
        elif s_color in i_color or i_color in s_color:
            score += 10
        else:
            # Check overlap of words (e.g. "dark blue" and "blue")
            s_words = set(s_color.split())
            i_words = set(i_color.split())
            overlap = s_words.intersection(i_words)
            if overlap:
                score += 8

    # 5. Location (Weight: 10)
    max_score += 10
    s_location = search.get('location', '').strip().lower()
    i_location = item['location'].strip().lower()
    if s_location and i_location:
        if s_location == i_location:
            score += 10
        elif s_location in i_location or i_location in s_location:
            score += 8
        else:
            # Word token overlap
            s_words = set(s_location.split())
            i_words = set(i_location.split())
            overlap = s_words.intersection(i_words)
            if overlap:
                score += 5 + min(5, len(overlap) * 2)
            else:
                ratio = difflib.SequenceMatcher(None, s_location, i_location).ratio()
                score += ratio * 8

    # 6. Date (Weight: 10)
    max_score += 10
    s_date_lost_str = search.get('date_lost', '').strip()
    i_date_found_str = item['date_found'].strip()
    
    if s_date_lost_str and i_date_found_str:
        try:
            # Parse dates (formats are typically YYYY-MM-DD)
            s_date = datetime.strptime(s_date_lost_str[:10], '%Y-%m-%d')
            i_date = datetime.strptime(i_date_found_str[:10], '%Y-%m-%d')
            
            delta = (i_date - s_date).days
            
            # Since item must be found AFTER or on the same day it was lost:
            if delta >= 0:
                if delta <= 2:
                    score += 10
                elif delta <= 7:
                    score += 8
                elif delta <= 14:
                    score += 5
                else:
                    score += 3
            else:
                # Found date is before lost date. Minor penalty but still possible due to user input errors
                abs_delta = abs(delta)
                if abs_delta <= 1:
                    score += 5  # Close enough (timezone/input estimation)
                elif abs_delta <= 3:
                    score += 2
        except Exception:
            # Fallback if date parsing fails
            pass
            
    # Calculate percentage
    if max_score == 0:
        return 0.0
    return round((score / max_score) * 100, 1)

def match_lost_item(search_params, found_items):
    """
    Matches a lost item against all found items and returns a list of items
    with their match scores and confidence tiers, sorted by score.
    """
    matched_results = []
    
    for item in found_items:
        # item is a dict or Row object
        score = calculate_match_score(search_params, item)
        
        # Categorize confidence tier
        if score >= 75:
            tier = 'High Match'
            tier_class = 'match-high'
        elif score >= 45:
            tier = 'Medium Match'
            tier_class = 'match-medium'
        elif score >= 20:
            tier = 'Low Match'
            tier_class = 'match-low'
        else:
            # Skip extremely low matches to avoid clutter, unless score is very low but non-zero, let's show it if score > 10
            if score < 10:
                continue
            tier = 'Weak Match'
            tier_class = 'match-weak'
            
        item_dict = dict(item)
        item_dict['match_score'] = score
        item_dict['match_tier'] = tier
        item_dict['match_tier_class'] = tier_class
        matched_results.append(item_dict)
        
    # Sort descending by match score
    matched_results.sort(key=lambda x: x['match_score'], reverse=True)
    return matched_results
