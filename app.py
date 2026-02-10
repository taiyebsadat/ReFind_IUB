import os
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from supabase import create_client, Client

app = Flask(__name__)

# --- SECURE CONFIGURATION ---
app.secret_key = os.environ.get('SECRET_KEY', 'university_secret_key')

# Get the database URL from Render's Environment Variable
db_url = os.environ.get('DATABASE_URL')

# Fallback for local testing (only if DATABASE_URL is not found)
if not db_url:
    raw_password = urllib.parse.quote_plus("ReFind@1097")
    db_url = f"postgresql://postgres:{raw_password}@db.wcwuwxebdimdzqshhlnd.supabase.co:5432/postgres"

# Render sometimes uses "postgres://", which SQLAlchemy requires to be "postgresql://"
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Config
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
# Your specific URL
SUPABASE_URL = "https://wcwuwxebdimdzqshhlnd.supabase.co"
# You MUST copy this from your Supabase API settings
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indjd3V3eGViZGltZHpxc2hobG5kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA3NDgzNjcsImV4cCI6MjA4NjMyNDM2N30.FkbInOQ8aLPVUzVi8c0Mr2gx1cp5YpDw3EHDLDQ_e58" 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- DATABASE INITIALIZATION ---
db = SQLAlchemy(app)

# --- ADMIN CREDENTIALS ---
AUTHORIZED_ADMINS = ['2412517']
ADMIN_ACCOUNTS = {
    "sadat": "sadat26",
    "fahad": "fahad2026"
    }

# --- MODELS ---

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100)) 
    items = db.relationship('Item', backref='reporter', lazy=True)
    # Relationship to easily find sender details in notifications
    sent_notifications = db.relationship('Notification', backref='sender', lazy=True)

class Item(db.Model):
    __tablename__ = 'item'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))        
    item_name = db.Column(db.String(100))
    owner_name = db.Column(db.String(100)) 
    target_id = db.Column(db.String(50))   
    location = db.Column(db.String(100))   
    description = db.Column(db.Text)       
    security_question = db.Column(db.String(200)) 

    # Link to User
    posted_by = db.Column(db.String(20), db.ForeignKey('user.user_id'), nullable=False)
    # Note: We removed the db.relationship line from here to fix the crash.
    
    # Change from String(100) to Text to fit the long URL
    image_file = db.Column(db.Text, default='https://wcwuwxebdimdzqshhlnd.supabase.co/storage/v1/object/public/item-images/default.jpg')
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)    
    resolved = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='Active') 
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.String(50), nullable=False)
    # Changed to ForeignKey so msg.sender.name works in dashboard
    sender_id = db.Column(db.String(50), db.ForeignKey('user.user_id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    contact_info = db.Column(db.String(255), nullable=True) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Added relationship to Item
    item = db.relationship('Item', backref='notifications')

class InfoRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    sender_id = db.Column(db.String(20), nullable=False)  
    receiver_id = db.Column(db.String(20), nullable=False) 
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True) 
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    sender_id = db.Column(db.String(50), nullable=False)
    receiver_id = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_read = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20)) # To store WhatsApp/Phone info

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_owner_id = db.Column(db.String(50), nullable=False)  # The person who posted the item
    asker_id = db.Column(db.String(50), nullable=False)       # The person asking the question
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)               # Starts empty until owner replies
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    is_resolved = db.Column(db.Boolean, default=False)
# --- DATABASE INITIALIZATION (CRITICAL FOR RENDER) ---
# This block runs every time the app starts, ensuring tables exist even if campus.db is missing.
with app.app_context():
    db.create_all()

# --- ROUTES ---
# (I am keeping all your existing route functions exactly as they are)

@app.route('/')
def index():
    if 'user_id' in session:
        # Use Student ID for admin check consistently
        if session['user_id'] in AUTHORIZED_ADMINS or session.get('is_admin'):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login')
def login():
    callback_url = url_for('auth_callback', _external=True)
    auth_url = f"https://iras-auth.pages.dev/login?redirect_uri={callback_url}"
    return redirect(auth_url)
'''
@app.route('/')
def index():
    if 'user_id' in session:
        # Use Student ID for admin check consistently
        if session['user_id'] == '2412517': 
            return redirect(url_for('admin_panel')p)
        return redirect(url_for('dashboard'))
    return render_template('index.html')
'''
@app.route('/callback')
def auth_callback():
    student_id = request.args.get('studentId')
    student_name = request.args.get('studentName')
    
    if student_id:
        session['user_id'] = student_id
        session['user_name'] = student_name
        
        user = User.query.filter_by(user_id=student_id).first()
        if not user:
            new_user = User(user_id=student_id, name=student_name)
            db.session.add(new_user)
            db.session.commit() # Ensure user is saved
            
        flash(f"Logged in as {student_name}", "success")
        
        # Consistent Admin Check
        if student_id in AUTHORIZED_ADMINS:
            session['is_admin'] = True  
            return redirect(url_for('admin_panel'))
            
        return redirect(url_for('dashboard'))
        
    flash("Authentication failed.", "danger")
    return redirect(url_for('index'))
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # 1. Items I reported
    my_reports = Item.query.filter_by(posted_by=user_id).all()
    
    # 2. Notifications/Claims for me (Probable ID hits)
    messages = Notification.query.filter_by(recipient_id=session['user_id']).all()    
    # 3. Questions asked TO ME (If I claimed something)
    # I am the asker_id, and I'm waiting to provide an answer
    questions_for_me = Inquiry.query.filter_by(asker_id=user_id, answer=None).all()
    
    # 4. Answers received (I posted an item, asked a question, and got a reply)
    incoming_answers = Inquiry.query.filter(Inquiry.item_owner_id == user_id, Inquiry.answer != None).all()

    return render_template('dashboard.html', 
                           my_reports=my_reports, 
                           messages=messages, 
                           questions_for_me=questions_for_me,
                           incoming_answers=incoming_answers)
    
@app.route('/report/<report_type>')
def report(report_type):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('report.html', report_type=report_type, item=None, edit_mode=False)

@app.route('/submit_report', methods=['POST'])
def submit_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    report_type = request.form.get('type')
    item_name = request.form.get('item_name')
    location = request.form.get('location')
    if location == 'Other':
        location = request.form.get('other_location')
    
    target_id = request.form.get('target_id')
    security_question = request.form.get('security_question')
    
    # --- UPDATED SUPABASE STORAGE LOGIC ---
    image_file = request.files.get('image')
    image_url = 'https://wcwuwxebdimdzqshhlnd.supabase.co/storage/v1/object/public/item-images/default.jpg'
    
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        
        # Read file as binary
        file_data = image_file.read()
        
        # Upload to Supabase Bucket 'item-images'
        try:
            supabase.storage.from_('item-images').upload(unique_name, file_data)
            # Get the Public URL
            image_url = supabase.storage.from_('item-images').get_public_url(unique_name)
        except Exception as e:
            flash(f"Image upload failed: {str(e)}", "danger")

    # Create the Item with the URL instead of filename
    new_item = Item(
        type=report_type,
        item_name=item_name,
        location=location,
        target_id=target_id,
        description=request.form.get('description'),
        security_question=security_question if report_type == 'Found' else None,
        image_file=image_url,  # Now storing the full URL
        posted_by=session['user_id'],
        date_posted=datetime.now(),
        status='Active'
    )
    
    db.session.add(new_item)
    db.session.commit()
    # ... rest of your code (notifications)
    
    db.session.add(new_item)
    db.session.commit()

    # --- PROBABLE ID NOTIFICATION ---
    if report_type == 'Found' and target_id:
        auto_msg = Notification(
            recipient_id=target_id,
            sender_id="System",
            item_id=new_item.id,
            message=f"Alert: An item matching your ID was found at {location}.",
            contact_info="Check your dashboard for details."
        )
        db.session.add(auto_msg)
        db.session.commit()

    flash(f"{report_type} report submitted successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/ask_question/<int:item_id>', methods=['POST'])
def ask_question(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    item = Item.query.get_or_404(item_id)
    claimant_id = request.form.get('claimant_id') # Passed from a hidden field in dashboard
    question_text = request.form.get('question')
    
    new_inquiry = Inquiry(
        item_id=item_id,
        item_owner_id=session['user_id'],
        asker_id=claimant_id,
        question=question_text
    )
    db.session.add(new_inquiry)
    db.session.commit()
    
    flash("Question sent to the claimant!", "success")
    return redirect(url_for('dashboard'))

@app.route('/admin_panel') # Changed from /admin to match your url_for calls
def admin_panel():
    # Allow access if it's your specific ID OR if the manual admin session is active
    is_authorized_id = session.get('user_id') in AUTHORIZED_ADMINS
    is_manual_admin = session.get('is_admin') == True
    
    if not (is_authorized_id or is_manual_admin):
        flash("Unauthorized access.", "danger")
        return redirect(url_for('dashboard'))
    current_tab = request.args.get('tab', 'active')
    search_query = request.args.get('search', '')
    
    query = Item.query
    if current_tab == 'resolved':
        query = query.filter_by(status='Resolved')
    else:
        query = query.filter(Item.status != 'Resolved')

    if search_query:
        query = query.filter((Item.item_name.ilike(f'%{search_query}%')) | (Item.posted_by.ilike(f'%{search_query}%')))
        
    items = query.order_by(Item.date_posted.desc()).all()
    total_active = Item.query.filter(Item.status != 'Resolved').count()
    total_resolved = Item.query.filter_by(status='Resolved').count()
    
    return render_template('admin.html', items=items, current_tab=current_tab, total_active=total_active, total_resolved=total_resolved, active='admin')

# --- ADMIN CREDENTIALS (MANUAL) ---
# --- MULTIPLE ADMIN CREDENTIALS ---
'''
AUTHORIZED_ADMINS = ['2412517']
ADMIN_ACCOUNTS = {
    "sadat": "sadat26",
    "fahad": "fahad2026",
    "moderator_refind": "manage_items_44"
}
'''
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username exists and password matches
        if username in ADMIN_ACCOUNTS and ADMIN_ACCOUNTS[username] == password:
            session['user_id'] = 'Admin'
            session['user_name'] = f"Admin ({username})"
            session['is_admin'] = True
            flash(f"Logged in as {username}", "success")
            return redirect(url_for('admin_panel'))
        
        flash("Invalid Username or Password", "danger")
    return render_template('admin_login.html')

@app.route('/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    item = Item.query.get_or_404(item_id)
    user_id = session.get('user_id')
    is_admin = session.get('is_admin') or user_id in AUTHORIZED_ADMINS
    
    if item.posted_by == user_id or is_admin:
        # If Admin deletes a student's post, notify them
        if is_admin and item.posted_by != user_id:
            admin_note = Notification(
                recipient_id=item.posted_by,
                sender_id='Admin',
                item_id=item.id,
                message=f"Your report for '{item.item_name}' was removed by an administrator for moderation."
            )
            db.session.add(admin_note)
        
        db.session.delete(item)
        db.session.commit()
        flash("Post deleted successfully.", "warning")
    else:
        flash("Unauthorized.", "danger")

    if is_admin:
        return redirect(url_for('admin_panel'))
    return redirect(url_for('dashboard'))

'''
@app.route('/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'is_admin' not in session:
        flash("Unauthorized", "danger")
        return redirect(url_for('index'))
        
    item = Item.query.get_or_404(item_id)
    
    # Notify user before deletion if it's not their own post
    if item.posted_by != session['user_id']:
        admin_note = Notification(
            recipient_id=item.posted_by,
            sender_id='Admin',
            item_id=item.id,
            message=f"Your report for '{item.item_name}' was removed by an administrator for moderation."
        )
        db.session.add(admin_note)
    
    db.session.delete(item)
    db.session.commit()
    flash("Item permanently deleted and user notified.", "warning")
    return redirect(url_for('admin_panel'))
'''
@app.route('/search')
def search():
    if 'user_id' not in session:
        flash("Please log in to search for items.", "warning")
        return redirect(url_for('login'))
    query = request.args.get('q', '')
    items = Item.query.filter(Item.item_name.ilike(f'%{query}%'), Item.resolved == False).all()
    return render_template('search_results.html', items=items, query=query)
'''
@app.route('/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    item = Item.query.get_or_404(item_id)
    user_id = session.get('user_id')
    
    # 🛑 Strict Security Check
    if item.posted_by == user_id or user_id == '2412517':
        db.session.delete(item)
        db.session.commit()
        flash("Post deleted successfully.", "success")
    else:
        # If someone tries to bypass the UI and delete via URL/POST
        flash("Access Denied: You cannot delete someone else's post.", "danger")
        return redirect(url_for('dashboard')), 403

    if user_id == '2412517':
        return redirect(url_for('admin_panel'))
    return redirect(url_for('dashboard'))
    item = Item.query.get_or_404(item_id)
    is_admin = session.get('user_id') == '2412517'
    
    # Check if user is owner OR admin
    if item.posted_by == session['user_id'] or is_admin:
        db.session.delete(item)
        db.session.commit()
        flash("Item removed successfully.", "success")
    else:
        flash("Unauthorized action.", "danger")
    
    # Redirect logic: If admin deleted it, stay in admin panel. 
    # Otherwise, go to dashboard.
    if is_admin:
        return redirect(url_for('admin_panel'))
    return redirect(url_for('dashboard'))

'''
@app.route('/delete_message/<int:msg_id>', methods=['POST'])
def delete_message(msg_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    message = Notification.query.get_or_404(msg_id)
    if str(message.recipient_id) == str(session['user_id']):
        db.session.delete(message)
        db.session.commit()
        flash("Message deleted successfully.", "info")
    else:
        flash("Unauthorized action.", "danger")
    return redirect(url_for('dashboard'))



@app.route('/resolve_item/<int:item_id>', methods=['POST'])
def resolve_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    item = Item.query.get_or_404(item_id)
    is_admin = session.get('user_id') == '2412517'
    
    # Allow if user is the one who posted it OR if it's the Admin
    if item.posted_by == session['user_id'] or is_admin:
        item.status = 'Resolved'
        db.session.commit()
        flash(f"Item '{item.item_name}' has been marked as resolved.", "success")
    else:
        flash("You do not have permission to resolve this item.", "danger")
    
    # If admin resolves from the Admin Panel, stay there
    if is_admin and request.referrer and 'admin' in request.referrer:
        return redirect(url_for('admin_panel'))
        
    return redirect(url_for('dashboard'))

@app.route('/claim_item/<int:item_id>', methods=['POST'])
def claim_item(item_id):
    if 'user_id' not in session:
        flash("Please log in to claim items.", "danger")
        return redirect(url_for('login'))
        
    item = Item.query.get_or_404(item_id)

    if item.posted_by == session.get('user_id'):
        flash("You cannot claim your own item!", "warning")
        return redirect(url_for('item_detail', item_id=item_id))

    new_notif = Notification(
        recipient_id=item.posted_by,
        sender_id=session['user_id'],
        item_id=item.id,
        message=request.form.get('message'),
        contact_info=request.form.get('contact_info')
    )
    db.session.add(new_notif)
    db.session.commit()
    flash("Claim request sent successfully.", "success")
    return redirect(url_for('item_detail', item_id=item.id))

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    messages = []
    
    if 'user_id' in session:
        # If I am the one who posted the item, show me ALL notifications for it
        if session['user_id'] == item.posted_by:
            messages = Notification.query.filter_by(item_id=item_id).all()
        else:
            # If I'm just a visitor, show only messages meant for me
            messages = Notification.query.filter_by(
                item_id=item_id, 
                recipient_id=session['user_id']
            ).all()
            
    return render_template('item_detail.html', item=item, messages=messages)

@app.route('/contact_poster/<int:item_id>', methods=['POST'])
def contact_poster(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    item = Item.query.get_or_404(item_id)
    sender = session['user_id']
    recipient = item.posted_by
    if str(sender) == str(recipient):
        flash("You cannot contact yourself!", "warning")
        return redirect(url_for('item_detail', item_id=item.id))
    new_notif = Notification(
        recipient_id=recipient,
        sender_id=sender,
        item_id=item.id,
        message=f"User {sender} is interested in your item: {item.item_name}"
    )
    db.session.add(new_notif)
    db.session.commit()
    flash(f"Notification sent to {recipient}!", "success")
    return redirect(url_for('item_detail', item_id=item.id))

@app.route('/ask_info/<int:item_id>', methods=['POST'])
def ask_info(item_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    item = Item.query.get_or_404(item_id)
    question_text = request.form.get('question')
    new_req = InfoRequest(
        item_id=item.id,
        sender_id=session['user_id'],
        receiver_id=item.posted_by,
        question=question_text
    )
    db.session.add(new_req)
    db.session.commit()
    return redirect(url_for('item_detail', item_id=item_id))

@app.route('/reply_info/<int:req_id>', methods=['POST'])
def reply_info(req_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    inquiry = Inquiry.query.get_or_404(req_id)
    answer_text = request.form.get('answer')
    
    if answer_text:
        inquiry.answer = answer_text
        db.session.commit()
        flash("Your answer has been sent!", "success")
    
    return redirect(url_for('dashboard'))

@app.route('/contact_item/<int:item_id>')
def contact_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    item = Item.query.get_or_404(item_id)
    return render_template('contact_page.html', item=item)

@app.route('/send_final_contact/<int:item_id>', methods=['POST'])
def send_final_contact(item_id):
    item = Item.query.get_or_404(item_id)
    phone = request.form.get('phone')
    fb = request.form.get('fb_link')
    contact_msg = f"User {session['user_id']} wants to claim '{item.item_name}'. Contact: {phone} | {fb}"
    new_notif = Notification(
        recipient_id=item.posted_by,
        sender_id=session['user_id'],
        item_id=item.id,
        message=contact_msg
    )
    db.session.add(new_notif)
    db.session.commit()
    flash("Your contact info has been sent to the poster!", "success")
    return redirect(url_for('dashboard'))

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    item = Item.query.get_or_404(item_id)
    
    # NEW: Prevent editing if resolved
    if item.status == 'Resolved':
        flash("This item is resolved and can no longer be edited.", "warning")
        return redirect(url_for('item_detail', item_id=item.id))

    is_admin = session.get('user_id') == '2412517'
    
    if str(item.posted_by) != str(session['user_id']) and not is_admin:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('item_detail', item_id=item.id))
        
    if request.method == 'POST':
        loc = request.form.get('location')
        item.location = request.form.get('other_location') if loc == 'Other' else loc
        item.item_name = request.form.get('item_name')
        item.owner_name = request.form.get('owner_name')
        item.target_id = request.form.get('target_id')
        item.description = request.form.get('description')
        item.security_question = request.form.get('security_question')
        db.session.commit()
        flash("Updated successfully!", "success")
        return redirect(url_for('item_detail', item_id=item.id))
        
    return render_template('report.html', item=item, report_type=item.type, edit_mode=True)

@app.route('/view_message/<int:notif_id>')
def view_message(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    msg = Notification.query.get_or_404(notif_id)
    item = Item.query.get(msg.item_id)
    return redirect(url_for('item_detail', item_id=msg.item_id))
@app.route('/more')
def more():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Fetch recent active found items for the slider
    found_items = Item.query.filter_by(type='Found', status='Active').order_by(Item.date_posted.desc()).limit(5).all()
    return render_template('more.html', found_items=found_items)

@app.route('/recent_reports')
def recent_reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Fetch all unresolved items, newest first
    items = Item.query.filter_by(resolved=False).order_by(Item.date_posted.desc()).all()
    return render_template('recent_reports.html', items=items)

@app.route('/portfolio')
def portfolio():
    # If logged in, home button goes to dashboard; otherwise, index
    home_destination = 'dashboard' if 'user_id' in session else 'index'
    return render_template('portfolio.html', home_destination=home_destination)

if __name__ == '__main__':
    app.run(debug=True)




