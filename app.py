import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db_connection, init_db
from matcher import match_lost_item

app = Flask(__name__)
app.secret_key = 'lost_and_found_premium_secret_key_2026'

# Configure upload folder
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Context processor to make active user information available globally in templates
@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        conn.close()
    return dict(current_user=user)

# ----------------- ROUTES -----------------

@app.route('/')
def index():
    conn = get_db_connection()
    # Fetch recently found items (limit to 6)
    items = conn.execute('''
        SELECT i.*, u.name as finder_name 
        FROM items i 
        JOIN users u ON i.finder_id = u.id 
        ORDER BY i.created_at DESC 
        LIMIT 6
    ''').fetchall()
    conn.close()
    return render_template('index.html', items=items)

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        phone = request.form.get('phone').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not name or not email or not phone or not password or not confirm_password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
            
        conn = get_db_connection()
        # Check if email already exists
        existing_user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        
        if existing_user:
            conn.close()
            flash('Email address already registered.', 'error')
            return render_template('register.html')
            
        # Create user
        hashed_password = generate_password_hash(password)
        try:
            conn.execute('''
                INSERT INTO users (name, email, phone, password_hash)
                VALUES (?, ?, ?, ?)
            ''', (name, email, phone, hashed_password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash(f'An error occurred: {str(e)}', 'error')
            
    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    next_page = request.args.get('next')
    
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html')
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

# User Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# Report Found Item
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user_id' not in session:
        flash('You must be logged in to report a found item.', 'error')
        return redirect(url_for('login', next=request.path))
        
    if request.method == 'POST':
        category = request.form.get('category')
        title = request.form.get('title').strip()
        brand = request.form.get('brand').strip()
        color = request.form.get('color').strip()
        date_found = request.form.get('date_found')
        location = request.form.get('location').strip()
        description = request.form.get('description').strip()
        verification_question = request.form.get('verification_question').strip()
        
        if not category or not title or not brand or not color or not date_found or not location or not verification_question:
            flash('Please fill in all required fields.', 'error')
            return render_template('report.html')
            
        # Handle image upload
        image_filename = None
        file = request.files.get('item_image')
        if file and file.filename != '':
            if allowed_file(file.filename):
                # Make filename unique
                import time
                filename = f"{int(time.time())}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
            else:
                flash('Invalid image format. Allowed formats: PNG, JPG, JPEG, GIF.', 'error')
                return render_template('report.html')
                
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO items (finder_id, category, title, brand, color, date_found, location, description, image_filename, verification_question)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], category, title, brand, color, date_found, location, description, image_filename, verification_question))
            conn.commit()
            conn.close()
            flash('Found item reported successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.close()
            flash(f'An error occurred: {str(e)}', 'error')
            
    return render_template('report.html')

# Search & Match
@app.route('/search')
def search():
    category = request.args.get('category', '').strip()
    title = request.args.get('title', '').strip()
    brand = request.args.get('brand', '').strip()
    color = request.args.get('color', '').strip()
    date_lost = request.args.get('date_lost', '').strip()
    location = request.args.get('location', '').strip()
    
    query_params = {
        'category': category,
        'title': title,
        'brand': brand,
        'color': color,
        'date_lost': date_lost,
        'location': location
    }
    
    has_searched = any(query_params.values())
    results = []
    
    if has_searched:
        conn = get_db_connection()
        # We only search against 'open' items
        found_items = conn.execute('''
            SELECT i.*, u.name as finder_name 
            FROM items i 
            JOIN users u ON i.finder_id = u.id 
            WHERE i.status = 'open'
        ''').fetchall()
        conn.close()
        
        # Match using matcher algorithm
        results = match_lost_item(query_params, found_items)
        
    return render_template('search.html', query_params=query_params, has_searched=has_searched, results=results)

# Item Details & Claim Setup
@app.route('/item/<int:item_id>')
def item_details(item_id):
    conn = get_db_connection()
    item = conn.execute('''
        SELECT i.*, u.name as finder_name 
        FROM items i 
        JOIN users u ON i.finder_id = u.id 
        WHERE i.id = ?
    ''', (item_id,)).fetchone()
    
    if not item:
        conn.close()
        flash('Item not found.', 'error')
        return redirect(url_for('index'))
        
    user_claim = None
    finder = None
    
    # If logged in, fetch user's claim status for this item
    if 'user_id' in session:
        user_claim = conn.execute('''
            SELECT * FROM claims 
            WHERE item_id = ? AND claimant_id = ?
        ''', (item_id, session['user_id'])).fetchone()
        
        # If user's claim is approved, fetch details of the finder to display
        if user_claim and user_claim['status'] == 'approved':
            finder = conn.execute('SELECT name, email, phone FROM users WHERE id = ?', (item['finder_id'],)).fetchone()
            
    conn.close()
    return render_template('item_details.html', item=item, user_claim=user_claim, finder=finder)

# Claim Submit Route
@app.route('/claim/<int:item_id>', methods=['POST'])
def claim_item(item_id):
    if 'user_id' not in session:
        flash('You must be logged in to claim an item.', 'error')
        return redirect(url_for('login'))
        
    verification_answer = request.form.get('verification_answer').strip()
    proof_description = request.form.get('proof_description').strip()
    
    if not verification_answer or not proof_description:
        flash('Please fill out all verification fields.', 'error')
        return redirect(url_for('item_details', item_id=item_id))
        
    conn = get_db_connection()
    
    # Verify item exists and user isn't the finder
    item = conn.execute('SELECT finder_id, status FROM items WHERE id = ?', (item_id,)).fetchone()
    if not item:
        conn.close()
        flash('Item not found.', 'error')
        return redirect(url_for('index'))
        
    if item['finder_id'] == session['user_id']:
        conn.close()
        flash("You cannot claim an item you reported as found.", 'error')
        return redirect(url_for('item_details', item_id=item_id))
        
    if item['status'] == 'claimed':
        conn.close()
        flash("This item has already been claimed.", 'error')
        return redirect(url_for('item_details', item_id=item_id))
        
    # Check if a claim already exists
    existing_claim = conn.execute('SELECT id, status FROM claims WHERE item_id = ? AND claimant_id = ?', (item_id, session['user_id'])).fetchone()
    
    try:
        if existing_claim:
            # Update existing claim (e.g. if they are resubmitting after a rejection)
            conn.execute('''
                UPDATE claims 
                SET verification_answer = ?, proof_description = ?, status = 'pending', created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (verification_answer, proof_description, existing_claim['id']))
            flash('Your claim details have been updated.', 'success')
        else:
            # Create a new claim
            conn.execute('''
                INSERT INTO claims (item_id, claimant_id, verification_answer, proof_description, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (item_id, session['user_id'], verification_answer, proof_description))
            flash('Your claim request has been submitted successfully!', 'success')
            
        conn.commit()
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('item_details', item_id=item_id))

# User Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You must be logged in to view your dashboard.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user_id = session['user_id']
    
    # 1. Fetch items reported by user
    reported_items_rows = conn.execute('''
        SELECT * FROM items 
        WHERE finder_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,)).fetchall()
    
    reported_items = []
    for item_row in reported_items_rows:
        item = dict(item_row)
        # Fetch claims for this item
        claims = conn.execute('''
            SELECT c.*, u.name as claimant_name, u.email as claimant_email, u.phone as claimant_phone 
            FROM claims c 
            JOIN users u ON c.claimant_id = u.id 
            WHERE c.item_id = ? 
            ORDER BY c.created_at DESC
        ''', (item['id'],)).fetchall()
        
        item['claims'] = [dict(c) for c in claims]
        reported_items.append(item)
        
    # 2. Fetch claims made by user
    claims_made = conn.execute('''
        SELECT c.*, i.title as item_title, i.category as item_category, u.name as finder_name
        FROM claims c 
        JOIN items i ON c.item_id = i.id 
        JOIN users u ON i.finder_id = u.id 
        WHERE c.claimant_id = ? 
        ORDER BY c.created_at DESC
    ''', (user_id,)).fetchall()
    
    conn.close()
    return render_template('dashboard.html', reported_items=reported_items, claims_made=claims_made)

# Approve Claim
@app.route('/claim/approve/<int:claim_id>', methods=['POST'])
def approve_claim(claim_id):
    if 'user_id' not in session:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    # Get the claim details and check if the current user is the finder of the item
    claim = conn.execute('''
        SELECT c.*, i.finder_id, i.id as item_id 
        FROM claims c 
        JOIN items i ON c.item_id = i.id 
        WHERE c.id = ?
    ''', (claim_id,)).fetchone()
    
    if not claim:
        conn.close()
        flash('Claim request not found.', 'error')
        return redirect(url_for('dashboard'))
        
    if claim['finder_id'] != session['user_id']:
        conn.close()
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))
        
    try:
        # 1. Approve this claim
        conn.execute("UPDATE claims SET status = 'approved' WHERE id = ?", (claim_id,))
        
        # 2. Reject all other pending claims for this item
        conn.execute("UPDATE claims SET status = 'rejected' WHERE item_id = ? AND id != ?", (claim['item_id'], claim_id))
        
        # 3. Mark the item as claimed
        conn.execute("UPDATE items SET status = 'claimed' WHERE id = ?", (claim['item_id'],))
        
        conn.commit()
        flash('Claim approved! The owner has been notified and contact details are shared.', 'success')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard'))

# Reject Claim
@app.route('/claim/reject/<int:claim_id>', methods=['POST'])
def reject_claim(claim_id):
    if 'user_id' not in session:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    # Get the claim details and check if the current user is the finder of the item
    claim = conn.execute('''
        SELECT c.*, i.finder_id 
        FROM claims c 
        JOIN items i ON c.item_id = i.id 
        WHERE c.id = ?
    ''', (claim_id,)).fetchone()
    
    if not claim:
        conn.close()
        flash('Claim request not found.', 'error')
        return redirect(url_for('dashboard'))
        
    if claim['finder_id'] != session['user_id']:
        conn.close()
        flash('Unauthorized access.', 'error')
        return redirect(url_for('dashboard'))
        
    try:
        # Reject the claim
        conn.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim_id,))
        conn.commit()
        flash('Claim request rejected.', 'info')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard'))

# ----------------- MAIN STARTUP -----------------

if __name__ == '__main__':
    # Initialize database tables on start
    init_db()
    # Run the application
    app.run(debug=True)
