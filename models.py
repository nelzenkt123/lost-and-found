import sqlite3
import os
from datetime import datetime

DATABASE_NAME = 'database.db'

def get_db_connection():
    """Establishes and returns a database connection with Row factory enabled."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(schema_path='schema.sql'):
    """Initializes the database using the schema.sql file if database tables do not exist."""
    db_exists = os.path.exists(DATABASE_NAME)
    
    # Check if schema file exists
    if not os.path.exists(schema_path):
        print(f"Error: Schema file not found at {schema_path}")
        return False
        
    conn = get_db_connection()
    try:
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        print("Database initialized successfully.")
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
    finally:
        conn.close()

# --- User Functions ---

def create_user(username, email, password_hash, is_admin=0):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, is_admin)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None  # Username or Email already exists
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user

def update_user_profile(user_id, email, password_hash=None):
    conn = get_db_connection()
    try:
        if password_hash:
            conn.execute(
                "UPDATE users SET email = ?, password_hash = ? WHERE id = ?",
                (email, password_hash, user_id)
            )
        else:
            conn.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (email, user_id)
            )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, email, is_admin, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return users

def delete_user(user_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False
    finally:
        conn.close()

# --- Item Functions ---

def report_lost_item(user_id, name, category, description, date_lost, location_lost, image_url, contact_name, contact_phone, contact_email):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO lost_items 
               (user_id, name, category, description, date_lost, location_lost, image_url, contact_name, contact_phone, contact_email) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, category, description, date_lost, location_lost, image_url, contact_name, contact_phone, contact_email)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error reporting lost item: {e}")
        return None
    finally:
        conn.close()

def report_found_item(user_id, name, category, description, date_found, location_found, image_url, contact_name, contact_phone, contact_email):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO found_items 
               (user_id, name, category, description, date_found, location_found, image_url, contact_name, contact_phone, contact_email) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, category, description, date_found, location_found, image_url, contact_name, contact_phone, contact_email)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error reporting found item: {e}")
        return None
    finally:
        conn.close()

def get_lost_item(item_id):
    conn = get_db_connection()
    item = conn.execute(
        """SELECT l.*, u.username as reporter_username 
           FROM lost_items l 
           JOIN users u ON l.user_id = u.id 
           WHERE l.id = ?""", (item_id,)
    ).fetchone()
    conn.close()
    return item

def get_found_item(item_id):
    conn = get_db_connection()
    item = conn.execute(
        """SELECT f.*, u.username as reporter_username 
           FROM found_items f 
           JOIN users u ON f.user_id = u.id 
           WHERE f.id = ?""", (item_id,)
    ).fetchone()
    conn.close()
    return item

def get_all_lost_items(active_only=False):
    conn = get_db_connection()
    query = "SELECT * FROM lost_items"
    if active_only:
        query += " WHERE is_resolved = 0"
    query += " ORDER BY created_at DESC"
    items = conn.execute(query).fetchall()
    conn.close()
    return items

def get_all_found_items(active_only=False):
    conn = get_db_connection()
    query = "SELECT * FROM found_items"
    if active_only:
        query += " WHERE is_resolved = 0"
    query += " ORDER BY created_at DESC"
    items = conn.execute(query).fetchall()
    conn.close()
    return items

def get_items_by_user(user_id):
    conn = get_db_connection()
    lost = conn.execute("SELECT * FROM lost_items WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    found = conn.execute("SELECT * FROM found_items WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return {'lost': lost, 'found': found}

def search_items(query_str, category=None, location=None, item_type=None, active_only=True):
    conn = get_db_connection()
    results = []
    
    # Setup conditions
    conditions = []
    params = []
    
    if active_only:
        conditions.append("is_resolved = 0")
        
    if category and category != 'All':
        conditions.append("category = ?")
        params.append(category)
        
    if location:
        conditions.append("location_lost LIKE ?") # Will adapt based on item_type below
        params.append(f"%{location}%")
        
    if query_str:
        conditions.append("(name LIKE ? OR description LIKE ?)")
        params.append(f"%{query_str}%")
        params.append(f"%{query_str}%")

    # Lost items search
    if not item_type or item_type == 'lost':
        lost_conds = list(conditions)
        lost_params = list(params)
        # Fix location variable name for lost items
        if location:
            for idx, c in enumerate(lost_conds):
                if "location_lost" in c:
                    lost_conds[idx] = "location_lost LIKE ?"
                    
        where_clause = " WHERE " + " AND ".join(lost_conds) if lost_conds else ""
        sql = f"SELECT *, 'lost' as type FROM lost_items{where_clause} ORDER BY created_at DESC"
        lost_results = conn.execute(sql, lost_params).fetchall()
        results.extend([dict(r) for r in lost_results])
        
    # Found items search
    if not item_type or item_type == 'found':
        found_conds = list(conditions)
        found_params = list(params)
        # Fix location variable name for found items
        if location:
            for idx, c in enumerate(found_conds):
                if "location_lost" in c:
                    found_conds[idx] = "location_found LIKE ?"
                    
        where_clause = " WHERE " + " AND ".join(found_conds) if found_conds else ""
        sql = f"SELECT *, 'found' as type FROM found_items{where_clause} ORDER BY created_at DESC"
        found_results = conn.execute(sql, found_params).fetchall()
        results.extend([dict(r) for r in found_results])
        
    conn.close()
    # Sort by created_at descending
    results.sort(key=lambda x: x['created_at'], reverse=True)
    return results

def resolve_lost_item(item_id, resolved=1):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE lost_items SET is_resolved = ? WHERE id = ?", (resolved, item_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error resolving lost item: {e}")
        return False
    finally:
        conn.close()

def resolve_found_item(item_id, resolved=1):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE found_items SET is_resolved = ? WHERE id = ?", (resolved, item_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error resolving found item: {e}")
        return False
    finally:
        conn.close()

def delete_lost_item(item_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM lost_items WHERE id = ?", (item_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting lost item: {e}")
        return False
    finally:
        conn.close()

def delete_found_item(item_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM found_items WHERE id = ?", (item_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting found item: {e}")
        return False
    finally:
        conn.close()


# --- Matching Functions ---

def create_match(lost_item_id, found_item_id, match_score):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO matches (lost_item_id, found_item_id, match_score) 
               VALUES (?, ?, ?) 
               ON CONFLICT(lost_item_id, found_item_id) 
               DO UPDATE SET match_score = excluded.match_score""",
            (lost_item_id, found_item_id, match_score)
        )
        conn.commit()
        return cursor.lastrowid or True
    except Exception as e:
        print(f"Error creating match record: {e}")
        return None
    finally:
        conn.close()

def get_match(match_id):
    conn = get_db_connection()
    match = conn.execute(
        """SELECT m.*, 
                  l.name as lost_name, l.category as lost_category, l.user_id as lost_user_id,
                  f.name as found_name, f.category as found_category, f.user_id as found_user_id
           FROM matches m
           JOIN lost_items l ON m.lost_item_id = l.id
           JOIN found_items f ON m.found_item_id = f.id
           WHERE m.id = ?""", (match_id,)
    ).fetchone()
    conn.close()
    return match

def get_matches_for_lost_item(lost_item_id):
    conn = get_db_connection()
    matches = conn.execute(
        """SELECT m.*, f.name, f.category, f.description, f.location_found, f.date_found, f.image_url, f.is_resolved 
           FROM matches m 
           JOIN found_items f ON m.found_item_id = f.id 
           WHERE m.lost_item_id = ? AND m.is_rejected = 0
           ORDER BY m.match_score DESC""", (lost_item_id,)
    ).fetchall()
    conn.close()
    return matches

def get_matches_for_found_item(found_item_id):
    conn = get_db_connection()
    matches = conn.execute(
        """SELECT m.*, l.name, l.category, l.description, l.location_lost, l.date_lost, l.image_url, l.is_resolved 
           FROM matches m 
           JOIN lost_items l ON m.lost_item_id = l.id 
           WHERE m.found_item_id = ? AND m.is_rejected = 0
           ORDER BY m.match_score DESC""", (found_item_id,)
    ).fetchall()
    conn.close()
    return matches

def get_all_matches():
    conn = get_db_connection()
    matches = conn.execute(
        """SELECT m.*, 
                  l.name as lost_name, l.id as lost_id,
                  f.name as found_name, f.id as found_id
           FROM matches m
           JOIN lost_items l ON m.lost_item_id = l.id
           JOIN found_items f ON m.found_item_id = f.id
           ORDER BY m.match_score DESC, m.created_at DESC"""
    ).fetchall()
    conn.close()
    return matches

def update_match_status(match_id, status_type, val):
    """Updates match approval or rejection status. status_type can be 'approve' or 'reject'."""
    conn = get_db_connection()
    try:
        if status_type == 'approve':
            conn.execute("UPDATE matches SET is_approved_by_user = ? WHERE id = ?", (val, match_id))
        elif status_type == 'reject':
            conn.execute("UPDATE matches SET is_rejected = ? WHERE id = ?", (val, match_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating match status: {e}")
        return False
    finally:
        conn.close()


# --- Notification Functions ---

def create_notification(user_id, message, match_id=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO notifications (user_id, message, match_id) VALUES (?, ?, ?)",
            (user_id, message, match_id)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None
    finally:
        conn.close()

def get_notifications_by_user(user_id, unread_only=False):
    conn = get_db_connection()
    query = "SELECT * FROM notifications WHERE user_id = ?"
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY created_at DESC"
    notifications = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return notifications

def mark_notification_as_read(notification_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return False
    finally:
        conn.close()

def mark_all_notifications_as_read(user_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error marking all notifications as read: {e}")
        return False
    finally:
        conn.close()
