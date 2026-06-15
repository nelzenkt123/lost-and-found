from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime

import models
import matching

app = Flask(__name__)
app.secret_key = 'findback_super_secret_key_session_key'

# Upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB upload limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on startup
with app.app_context():
    models.init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Context processor to inject notification counts into templates automatically
@app.context_processor
def inject_globals():
    now_date = datetime.now().strftime("%Y-%m-%d")
    if 'user_id' in session:
        notifs = models.get_notifications_by_user(session['user_id'], unread_only=True)
        return {
            'unread_count': len(notifs),
            'now_date': now_date
        }
    return {
        'unread_count': 0,
        'now_date': now_date
    }

# --- Core Routes ---

@app.route('/')
def index():
    # 1. Fetch dashboard count stats
    conn = models.get_db_connection()
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    lost_count = conn.execute("SELECT COUNT(*) FROM lost_items WHERE is_resolved = 0").fetchone()[0]
    found_count = conn.execute("SELECT COUNT(*) FROM found_items WHERE is_resolved = 0").fetchone()[0]
    resolved_count = conn.execute("SELECT COUNT(*) FROM (SELECT id FROM lost_items WHERE is_resolved = 1 UNION ALL SELECT id FROM found_items WHERE is_resolved = 1)").fetchone()[0]
    matches_count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    conn.close()
    
    stats = {
        'users_count': users_count,
        'lost_count': lost_count,
        'found_count': found_count,
        'resolved_count': resolved_count,
        'matches_count': matches_count
    }
    
    # 2. Fetch recent reports (both types, resolved=0, sorted by date)
    recent_items = models.search_items(query_str=None, active_only=True)[:6]
    
    return render_template('index.html', stats=stats, recent_items=recent_items)

# --- Authentication ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('profile'))
        
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        
        if len(username) < 4:
            flash("Username must be at least 4 characters long.", "error")
            return render_template('register.html')
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template('register.html')
            
        password_hash = generate_password_hash(password)
        
        # Check if it is the first user, make them Admin automatically for convenience
        conn = models.get_db_connection()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        
        is_admin = 1 if user_count == 0 else 0
        
        user_id = models.create_user(username, email, password_hash, is_admin)
        
        if user_id:
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Username or email already exists.", "error")
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('profile'))
        
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        user = models.get_user_by_username(username)
        if not user:
            # Fallback to check email
            user = models.get_user_by_email(username)
            
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['is_admin'] = bool(user['is_admin'])
            
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('profile'))
        else:
            flash("Invalid username or password.", "error")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash("Please log in to view your profile.", "info")
        return redirect(url_for('login'))
        
    user = models.get_user_by_id(session['user_id'])
    items = models.get_items_by_user(session['user_id'])
    
    return render_template('profile.html', user=user, items=items)

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    email = request.form['email'].strip()
    password = request.form['password']
    
    password_hash = None
    if password:
        if len(password) < 6:
            flash("New password must be at least 6 characters.", "error")
            return redirect(url_for('profile'))
        password_hash = generate_password_hash(password)
        
    success = models.update_user_profile(session['user_id'], email, password_hash)
    if success:
        session['email'] = email
        flash("Profile updated successfully.", "success")
    else:
        flash("Email address is already in use by another account.", "error")
        
    return redirect(url_for('profile'))

# --- Reporting ---

@app.route('/report/lost', methods=['GET', 'POST'])
def report_lost():
    if 'user_id' not in session:
        flash("You must be logged in to report a lost item.", "info")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']
        description = request.form['description'].strip()
        date_lost = request.form['date_lost']
        location_lost = request.form['location_lost'].strip()
        
        contact_name = request.form['contact_name'].strip()
        contact_phone = request.form['contact_phone'].strip()
        contact_email = request.form['contact_email'].strip()
        
        # File upload handling
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Avoid filename collisions by prefixing UUID
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                image_url = unique_filename
                
        item_id = models.report_lost_item(
            session['user_id'], name, category, description, date_lost, location_lost,
            image_url, contact_name, contact_phone, contact_email
        )
        
        if item_id:
            flash("Lost item report submitted successfully!", "success")
            # Run the matching algorithm automatically
            matching.find_matches_for_item(item_id, 'lost')
            return redirect(url_for('item_detail', item_type='lost', item_id=item_id))
        else:
            flash("Failed to submit report. Please try again.", "error")
            
    return render_template('report_lost.html', user_email=session['email'])

@app.route('/report/found', methods=['GET', 'POST'])
def report_found():
    if 'user_id' not in session:
        flash("You must be logged in to report a found item.", "info")
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name'].strip()
        category = request.form['category']
        description = request.form['description'].strip()
        date_found = request.form['date_found']
        location_found = request.form['location_found'].strip()
        
        contact_name = request.form['contact_name'].strip()
        contact_phone = request.form['contact_phone'].strip()
        contact_email = request.form['contact_email'].strip()
        
        # File upload handling
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                image_url = unique_filename
                
        item_id = models.report_found_item(
            session['user_id'], name, category, description, date_found, location_found,
            image_url, contact_name, contact_phone, contact_email
        )
        
        if item_id:
            flash("Found item report submitted successfully!", "success")
            # Run matching
            matching.find_matches_for_item(item_id, 'found')
            return redirect(url_for('item_detail', item_type='found', item_id=item_id))
        else:
            flash("Failed to submit report. Please try again.", "error")
            
    return render_template('report_found.html', user_email=session['email'])

# --- Search & Browse ---

@app.route('/items')
def items():
    query = request.args.get('query', '').strip()
    category = request.args.get('category', 'All')
    location = request.args.get('location', '').strip()
    item_type = request.args.get('item_type', 'all')
    
    search_params = {
        'query': query,
        'category': category,
        'location': location,
        'item_type': item_type
    }
    
    # Run database search logic
    results = models.search_items(
        query_str=query if query else None,
        category=category if category != 'All' else None,
        location=location if location else None,
        item_type=item_type if item_type != 'all' else None,
        active_only=True
    )
    
    return render_template('items.html', items=results, search_params=search_params)

@app.route('/item/<item_type>/<int:item_id>')
def item_detail(item_type, item_id):
    if item_type == 'lost':
        item = models.get_lost_item(item_id)
        matches = models.get_matches_for_lost_item(item_id) if item else []
    elif item_type == 'found':
        item = models.get_found_item(item_id)
        matches = models.get_matches_for_found_item(item_id) if item else []
    else:
        return redirect(url_for('items'))
        
    if not item:
        flash("Item report not found.", "error")
        return redirect(url_for('items'))
        
    return render_template('item_detail.html', item=item, item_type=item_type, matches=matches)

@app.route('/item/<item_type>/<int:item_id>/resolve', methods=['POST'])
def toggle_resolve_item(item_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if item_type == 'lost':
        item = models.get_lost_item(item_id)
    else:
        item = models.get_found_item(item_id)
        
    if not item or item['user_id'] != session['user_id']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('profile'))
        
    new_status = 0 if item['is_resolved'] else 1
    
    if item_type == 'lost':
        models.resolve_lost_item(item_id, new_status)
    else:
        models.resolve_found_item(item_id, new_status)
        
    flash(f"Report status changed to {'Resolved' if new_status else 'Active'}.", "success")
    
    # If set back to active, trigger recompute
    if new_status == 0:
        matching.find_matches_for_item(item_id, item_type)
        
    return redirect(request.referrer or url_for('profile'))

@app.route('/item/<item_type>/<int:item_id>/delete', methods=['POST'])
def delete_item(item_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if item_type == 'lost':
        item = models.get_lost_item(item_id)
    else:
        item = models.get_found_item(item_id)
        
    if not item or item['user_id'] != session['user_id']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('profile'))
        
    # Delete image file if it exists
    if item['image_url']:
        try:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], item['image_url'])
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"Error removing image: {e}")
            
    if item_type == 'lost':
        models.delete_lost_item(item_id)
    else:
        models.delete_found_item(item_id)
        
    flash("Report deleted successfully.", "success")
    return redirect(url_for('profile'))

# --- Match Approvals ---

@app.route('/match/confirm/<int:match_id>/<item_type>/<int:item_id>', methods=['POST'])
def confirm_match(match_id, item_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    match = models.get_match(match_id)
    if not match:
        flash("Match record not found.", "error")
        return redirect(url_for('item_detail', item_type=item_type, item_id=item_id))
        
    # User must be owner of either the lost or found item
    if match['lost_user_id'] != session['user_id'] and match['found_user_id'] != session['user_id']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('index'))
        
    models.update_match_status(match_id, 'approve', 1)
    
    # Notify the opposite user that match was approved/confirmed!
    other_user_id = match['found_user_id'] if session['user_id'] == match['lost_user_id'] else match['lost_user_id']
    msg = f"Match confirmed! User {session['username']} confirmed the match between '{match['lost_name']}' and '{match['found_name']}'. Check contact details to reunite."
    models.create_notification(other_user_id, msg, match_id)
    
    flash("Match suggestion approved! Reach out to the reporter using the contact info.", "success")
    return redirect(url_for('item_detail', item_type=item_type, item_id=item_id))

@app.route('/match/reject/<int:match_id>/<item_type>/<int:item_id>', methods=['POST'])
def reject_match(match_id, item_type, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    match = models.get_match(match_id)
    if not match:
        flash("Match record not found.", "error")
        return redirect(url_for('item_detail', item_type=item_type, item_id=item_id))
        
    if match['lost_user_id'] != session['user_id'] and match['found_user_id'] != session['user_id']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('index'))
        
    models.update_match_status(match_id, 'reject', 1)
    flash("Match suggestion dismissed.", "info")
    return redirect(url_for('item_detail', item_type=item_type, item_id=item_id))

# --- Notifications ---

@app.route('/notifications')
def notifications_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    notifications = models.get_notifications_by_user(session['user_id'])
    return render_template('notifications.html', notifications=notifications)

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
def mark_read(notif_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
    success = models.mark_notification_as_read(notif_id)
    return jsonify({'success': success})

@app.route('/notifications/read-all', methods=['POST'])
def mark_all_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    models.mark_all_notifications_as_read(session['user_id'])
    flash("All notifications marked as read.", "success")
    return redirect(url_for('notifications_page'))

@app.route('/notifications/delete/<int:notif_id>', methods=['POST'])
def delete_notification(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = models.get_db_connection()
    try:
        conn.execute("DELETE FROM notifications WHERE id = ? AND user_id = ?", (notif_id, session['user_id']))
        conn.commit()
    except Exception as e:
        print(f"Error deleting notification: {e}")
    finally:
        conn.close()
        
    return redirect(url_for('notifications_page'))

# --- Admin Panel ---

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session['is_admin']:
        flash("Access denied. Admin permissions required.", "error")
        return redirect(url_for('index'))
        
    users = models.get_all_users()
    matches = models.get_all_matches()
    
    # Retrieve all items (lost + found)
    lost_items = models.get_all_lost_items(active_only=False)
    found_items = models.get_all_found_items(active_only=False)
    
    reports = []
    for l in lost_items:
        r = dict(l)
        r['type'] = 'lost'
        reports.append(r)
    for f in found_items:
        r = dict(f)
        r['type'] = 'found'
        reports.append(r)
        
    # Sort reports by created_at desc
    reports.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Calculate statistics
    conn = models.get_db_connection()
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    lost_count = conn.execute("SELECT COUNT(*) FROM lost_items").fetchone()[0]
    found_count = conn.execute("SELECT COUNT(*) FROM found_items").fetchone()[0]
    resolved_count = conn.execute("SELECT COUNT(*) FROM (SELECT id FROM lost_items WHERE is_resolved = 1 UNION ALL SELECT id FROM found_items WHERE is_resolved = 1)").fetchone()[0]
    conn.close()
    
    stats = {
        'users_count': users_count,
        'lost_count': lost_count,
        'found_count': found_count,
        'resolved_count': resolved_count
    }
    
    # Injected charts data
    category_counts = {}
    for r in reports:
        cat = r['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
        
    return render_template(
        'admin.html',
        users=users,
        reports=reports,
        matches=matches,
        stats=stats,
        cat_chart_data=category_counts
    )

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session or not session['is_admin']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('index'))
        
    if user_id == session['user_id']:
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for('admin_dashboard'))
        
    success = models.delete_user(user_id)
    if success:
        flash("User and all their reports deleted successfully.", "success")
    else:
        flash("Failed to delete user.", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-report/<item_type>/<int:item_id>', methods=['POST'])
def admin_delete_report(item_type, item_id):
    if 'user_id' not in session or not session['is_admin']:
        flash("Unauthorized action.", "error")
        return redirect(url_for('index'))
        
    if item_type == 'lost':
        item = models.get_lost_item(item_id)
    else:
        item = models.get_found_item(item_id)
        
    if not item:
        flash("Report not found.", "error")
        return redirect(url_for('admin_dashboard'))
        
    # Delete image if exists
    if item['image_url']:
        try:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], item['image_url'])
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"Error removing image: {e}")
            
    if item_type == 'lost':
        models.delete_lost_item(item_id)
    else:
        models.delete_found_item(item_id)
        
    flash("Report removed by administrator moderation.", "success")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
