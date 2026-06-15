import re
from datetime import datetime
import models

STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at', 'from', 
    'by', 'on', 'in', 'of', 'to', 'for', 'with', 'about', 'against', 'between', 'into', 
    'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 
    'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'all', 'any', 
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 
    'don', 'should', 'now', 'i', 'my', 'me', 'we', 'our', 'you', 'your', 'he', 'him', 
    'his', 'she', 'her', 'it', 'its', 'they', 'them', 'their'
}

def clean_text_and_tokenize(text):
    """Cleans punctuation, converts to lowercase, and extracts alphanumeric words."""
    if not text:
        return set()
    words = re.findall(r'\b\w{3,}\b', text.lower())
    return {word for word in words if word not in STOP_WORDS}

def calculate_match_score(lost_item, found_item):
    """
    Computes a score between 0 and 100 indicating likelihood of a match.
    Category must match, otherwise score is 0.
    """
    # 1. Category check (Hard requirement)
    if lost_item['category'].strip().lower() != found_item['category'].strip().lower():
        return 0
        
    score = 30  # Category match base points
    
    # 2. Location similarity (Max: 25 points)
    loc_lost = lost_item['location_lost'].strip().lower()
    loc_found = found_item['location_found'].strip().lower()
    
    if loc_lost == loc_found:
        score += 25
    elif loc_lost in loc_found or loc_found in loc_lost:
        score += 20
    else:
        # Tokenize locations and find intersection
        words_lost_loc = clean_text_and_tokenize(loc_lost)
        words_found_loc = clean_text_and_tokenize(loc_found)
        loc_intersection = words_lost_loc.intersection(words_found_loc)
        if loc_intersection:
            score += 15
            
    # 3. Keyword / Title & Description Overlap (Max: 30 points)
    name_lost = lost_item['name'].strip().lower()
    name_found = found_item['name'].strip().lower()
    
    # Title exact match
    title_match_points = 0
    if name_lost == name_found:
        title_match_points = 15
    elif name_lost in name_found or name_found in name_lost:
        title_match_points = 10
        
    # Text overlap
    desc_lost = lost_item['description'] or ""
    desc_found = found_item['description'] or ""
    
    tokens_lost = clean_text_and_tokenize(name_lost + " " + desc_lost)
    tokens_found = clean_text_and_tokenize(name_found + " " + desc_found)
    
    token_intersection = tokens_lost.intersection(tokens_found)
    overlap_points = 0
    if tokens_lost or tokens_found:
        min_len = min(len(tokens_lost), len(tokens_found))
        if min_len > 0:
            overlap_ratio = len(token_intersection) / min_len
            overlap_points = min(15, int(overlap_ratio * 15))
            
    score += (title_match_points + overlap_points)

    # 4. Date Proximity (Max: 15 points)
    try:
        # Expected formats: YYYY-MM-DD
        date_l = datetime.strptime(lost_item['date_lost'], "%Y-%m-%d")
        date_f = datetime.strptime(found_item['date_found'], "%Y-%m-%d")
        
        delta_days = (date_f - date_l).days
        
        if 0 <= delta_days <= 3:
            score += 15
        elif 4 <= delta_days <= 7:
            score += 10
        elif 8 <= delta_days <= 14:
            score += 5
        elif 15 <= delta_days <= 30:
            score += 2
        elif delta_days < 0:
            # Found date is before lost date
            if delta_days >= -2:
                # Small logging error, neutral
                score += 0
            else:
                # Found way before lost (highly unlikely match)
                score -= 25
    except Exception:
        # If dates are missing or fail parsing, give minor default points
        score += 5
        
    # Boundary constraints
    return max(0, min(100, score))

def find_matches_for_item(item_id, item_type):
    """
    Triggered when a new item is reported.
    Compares the new item with all opposite type items and records matches >= 50.
    """
    if item_type == 'lost':
        new_item = models.get_lost_item(item_id)
        if not new_item or new_item['is_resolved']:
            return
        opposite_items = models.get_all_found_items(active_only=True)
    else:
        new_item = models.get_found_item(item_id)
        if not new_item or new_item['is_resolved']:
            return
        opposite_items = models.get_all_lost_items(active_only=True)
        
    if not new_item:
        return
        
    new_item_dict = dict(new_item)
    
    for opp_item in opposite_items:
        opp_item_dict = dict(opp_item)
        
        # Identify lost and found roles
        if item_type == 'lost':
            lost_item = new_item_dict
            found_item = opp_item_dict
        else:
            lost_item = opp_item_dict
            found_item = new_item_dict
            
        score = calculate_match_score(lost_item, found_item)
        
        if score >= 50:
            # Create or update match
            match_id = models.create_match(lost_item['id'], found_item['id'], score)
            
            if match_id:
                # Notify both reporters if they are different users
                if lost_item['user_id'] != found_item['user_id']:
                    # Notify lost item owner
                    lost_msg = f"Match alert! A found item '{found_item['name']}' matches your lost report '{lost_item['name']}' (Match Score: {score}%)."
                    models.create_notification(lost_item['user_id'], lost_msg, match_id if isinstance(match_id, int) else None)
                    
                    # Notify found item owner
                    found_msg = f"Match alert! A lost report '{lost_item['name']}' matches your found report '{found_item['name']}' (Match Score: {score}%)."
                    models.create_notification(found_item['user_id'], found_msg, match_id if isinstance(match_id, int) else None)

def recompute_all_matches():
    """
    Clears existing unresolved matches and recreates them. Useful for admin operations 
    or when sample data is loaded.
    """
    conn = models.get_db_connection()
    try:
        # Only clear suggested matches that are NOT user-approved or rejected
        conn.execute("DELETE FROM matches WHERE is_approved_by_user = 0 AND is_rejected = 0")
        conn.commit()
    except Exception as e:
        print(f"Error resetting matches: {e}")
    finally:
        conn.close()
        
    lost_items = models.get_all_lost_items(active_only=True)
    found_items = models.get_all_found_items(active_only=True)
    
    for l in lost_items:
        l_dict = dict(l)
        for f in found_items:
            f_dict = dict(f)
            score = calculate_match_score(l_dict, f_dict)
            if score >= 50:
                models.create_match(l_dict['id'], f_dict['id'], score)
                # (Optional) notifications aren't re-sent for all items during a full clean recompute 
                # to prevent notification spam, but can be added if desired.
