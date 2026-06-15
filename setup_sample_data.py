import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

import models
import matching

def clear_existing_data():
    """Removes the database file and uploaded files directory to start fresh."""
    db_path = models.DATABASE_NAME
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print(f"Removed existing database file: {db_path}")
        except Exception as e:
            print(f"Error removing database file: {e}")
            
    # Clean static uploads folder
    uploads_dir = os.path.join('static', 'uploads')
    if os.path.exists(uploads_dir):
        try:
            shutil.rmtree(uploads_dir)
            os.makedirs(uploads_dir)
            print("Cleared existing uploads directory.")
        except Exception as e:
            print(f"Error clearing uploads directory: {e}")

def seed_data():
    print("Seeding sample data...")
    
    # 1. Clear database and files
    clear_existing_data()
    
    # 2. Reinitialize database structure
    if not models.init_db():
        print("Database initialization failed. Aborting seeder.")
        return
        
    # 3. Create Sample Users
    admin_pw = generate_password_hash("admin123")
    alice_pw = generate_password_hash("alice123")
    bob_pw = generate_password_hash("bob123")
    
    admin_id = models.create_user("admin", "admin@findback.com", admin_pw, is_admin=1)
    alice_id = models.create_user("alice", "alice@example.com", alice_pw, is_admin=0)
    bob_id = models.create_user("bob", "bob@example.com", bob_pw, is_admin=0)
    
    if not all([admin_id, alice_id, bob_id]):
        print("Failed to create sample users.")
        return
        
    print(f"Users created successfully: admin (ID:{admin_id}), alice (ID:{alice_id}), bob (ID:{bob_id})")

    # Dates configurations (e.g. 5 days ago, 4 days ago, etc.)
    today = datetime.now()
    date_5_days_ago = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    date_4_days_ago = (today - timedelta(days=4)).strftime("%Y-%m-%d")
    date_3_days_ago = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    date_2_days_ago = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    date_1_day_ago = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_today = today.strftime("%Y-%m-%d")

    # 4. Insert Lost Items (Alice & Bob)
    # Item 1: Alice lost a wallet
    lost_item1_id = models.report_lost_item(
        user_id=alice_id,
        name="Black Leather Wallet",
        category="Valuables",
        description="A black leather bifold wallet with a silver logo badge on the front. Contains my student library card, driver's license, and about $40 in cash. Misplaced during lunchtime.",
        date_lost=date_3_days_ago,
        location_lost="Science Building Cafeteria",
        image_url=None,
        contact_name="Alice Smith",
        contact_phone="+1 555-0101",
        contact_email="alice@example.com"
    )
    
    # Item 2: Bob lost a phone
    lost_item2_id = models.report_lost_item(
        user_id=bob_id,
        name="Apple iPhone 13 Pro",
        category="Electronics",
        description="Sierra Blue color iPhone 13 Pro in a clear protective case. The lock screen wallpaper is a golden retriever dog standing on green grass. Phone is locked.",
        date_lost=date_5_days_ago,
        location_lost="Campus Main Quad near the water fountain",
        image_url=None,
        contact_name="Bob Rogers",
        contact_phone="+1 555-0102",
        contact_email="bob@example.com"
    )
    
    # Item 3: Alice lost a textbook
    lost_item3_id = models.report_lost_item(
        user_id=alice_id,
        name="Chemistry Textbook",
        category="Books & Stationery",
        description="Organic Chemistry by Wade, 9th Edition. Hardcover with a drawing of chemical models on the front. Has 'Alice Smith' written in black marker on the top of the inside cover page.",
        date_lost=date_1_day_ago,
        location_lost="Library Study Room B (2nd Floor)",
        image_url=None,
        contact_name="Alice Smith",
        contact_phone="+1 555-0101",
        contact_email="alice@example.com"
    )

    # 5. Insert Found Items
    # Item 1: Bob found a wallet (matches Alice's wallet)
    found_item1_id = models.report_found_item(
        user_id=bob_id,
        name="Black Leather Cardholder / Wallet",
        category="Valuables",
        description="Found a small black leather wallet on one of the wooden dining tables in the science building cafe area. Looks like it has a student license inside and some cash. Contact me to confirm the name on the ID card.",
        date_found=date_2_days_ago,
        location_found="Science Building Cafe tables",
        image_url=None,
        contact_name="Bob Rogers",
        contact_phone="+1 555-0102",
        contact_email="bob@example.com"
    )
    
    # Item 2: Alice found a phone (matches Bob's phone)
    found_item2_id = models.report_found_item(
        user_id=alice_id,
        name="Sierra Blue iPhone in clear case",
        category="Electronics",
        description="Found a blue Apple iPhone resting on the bench near the central campus fountain. The lock screen shows a retriever dog photo. It is powered on but locked.",
        date_found=date_4_days_ago,
        location_found="Campus Fountain benches",
        image_url=None,
        contact_name="Alice Smith",
        contact_phone="+1 555-0101",
        contact_email="alice@example.com"
    )
    
    # Item 3: Bob found a chemistry textbook
    found_item3_id = models.report_found_item(
        user_id=bob_id,
        name="Organic Chemistry Textbook",
        category="Books & Stationery",
        description="Found a Wade Organic Chemistry 9th Edition book left behind in library study room B. Checking if the owner is still around. It has some writing on the inside cover.",
        date_found=date_1_day_ago,
        location_found="Library Study Rooms Area",
        image_url=None,
        contact_name="Bob Rogers",
        contact_phone="+1 555-0102",
        contact_email="bob@example.com"
    )
    
    # Item 4: Bob found car keys (unmatched item)
    found_item4_id = models.report_found_item(
        user_id=bob_id,
        name="Toyota Car Keys Keychain",
        category="Keys",
        description="Toyota fob key with a red leather loop keychain. Found in the parking lot G near block D.",
        date_found=date_today,
        location_found="Parking Lot G",
        image_url=None,
        contact_name="Bob Rogers",
        contact_phone="+1 555-0102",
        contact_email="bob@example.com"
    )

    print("Items inserted. Running matching engine to pre-calculate matches...")
    
    # 6. Recompute matches
    matching.recompute_all_matches()
    
    # Check created matches
    matches = models.get_all_matches()
    print(f"Computed {len(matches)} match recommendations.")
    for m in matches:
        print(f"  - Match found: '{m['lost_name']}' & '{m['found_name']}' with score: {m['match_score']}%")

    print("\nDatabase seeded successfully!")
    print("Credentials to test:")
    print("  - Admin: username=admin, password=admin123")
    print("  - Alice (User 1): username=alice, password=alice123")
    print("  - Bob (User 2): username=bob, password=bob123")

if __name__ == '__main__':
    seed_data()
