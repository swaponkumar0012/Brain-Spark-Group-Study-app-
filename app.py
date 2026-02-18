import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, join_room, leave_room, emit
from models import db, User, Group, GroupMember, StudyMaterial, Question, QuizAttempt, ChatMessage

app = Flask(__name__)
socketio = SocketIO(app)
app.config['SECRET_KEY'] = 'dev-secret-key-change-this' # Change for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'quiz.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure instance and upload folders exist
os.makedirs('instance', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth'))

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'register':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role') # 'student' or 'teacher'
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists.', 'error')
            else:
                is_teacher = (role == 'teacher')
                user = User(username=username, 
                            password_hash=generate_password_hash(password),
                            is_teacher=is_teacher)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for('dashboard'))
                
        elif action == 'login':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'error')
                
    return render_template('auth.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth'))

@app.route('/dashboard')
@login_required
def dashboard():
    my_groups = []
    if current_user.is_teacher:
        my_groups = Group.query.filter_by(created_by_id=current_user.id).all()
    else:
        memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
        my_groups = [m.group for m in memberships]
    return render_template('dashboard.html', user=current_user, groups=my_groups)

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    if not current_user.is_teacher:
        return redirect(url_for('dashboard'))
    
    name = request.form.get('name')
    if name:
        group = Group(name=name, created_by_id=current_user.id)
        db.session.add(group)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_group/<int:group_id>', methods=['POST'])
@login_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    if not current_user.is_teacher or group.created_by_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('dashboard'))

    # Delete associated members (if not handled by cascade)
    GroupMember.query.filter_by(group_id=group.id).delete()
    
    # Delete the group
    db.session.delete(group)
    db.session.commit()
    flash('Group deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/join_group', methods=['POST'])
@login_required
def join_group():
    group_id = request.form.get('group_id')
    group = Group.query.get(group_id)
    if group:
        if not GroupMember.query.filter_by(user_id=current_user.id, group_id=group.id).first():
            member = GroupMember(user_id=current_user.id, group_id=group.id)
            db.session.add(member)
            db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/group/<int:group_id>')
@login_required
def group_view(group_id):
    group = Group.query.get_or_404(group_id)
    # Check access
    if group.created_by_id != current_user.id:
        if not GroupMember.query.filter_by(user_id=current_user.id, group_id=group.id).first():
            flash("Access denied", "error")
            return redirect(url_for('dashboard'))
    
    materials = StudyMaterial.query.filter_by(group_id=group.id).all()
    return render_template('group_view.html', group=group, materials=materials)

@app.route('/group/<int:group_id>/upload', methods=['POST'])
@login_required
def upload_material(group_id):
    group = Group.query.get_or_404(group_id)
    if group.created_by_id != current_user.id:
        return redirect(url_for('dashboard'))
        
    if 'pdf_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('group_view', group_id=group_id))
        
    file = request.files['pdf_file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('group_view', group_id=group_id))
        
    if file:
        filename = secure_filename(file.filename)
        # Unique filename using timestamp to avoid collisions could be better, but simple for now
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        material = StudyMaterial(
            group_id=group.id,
            title=request.form.get('title'),
            pdf_filename=filename,
            reading_time_seconds=int(request.form.get('reading_time')),
            quiz_time_seconds=int(request.form.get('quiz_time'))
        )
        db.session.add(material)
        db.session.commit()
        
    return redirect(url_for('group_view', group_id=group_id))

@app.route('/material/<int:material_id>/delete', methods=['POST'])
@login_required
def delete_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    if material.group.created_by_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
        
    # Optional: Delete actual file from disk
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], material.pdf_filename))
    except:
        pass
        
    db.session.delete(material)
    db.session.commit()
    return redirect(url_for('group_view', group_id=material.group_id))

@app.route('/manage_questions/<int:material_id>')
@login_required
def manage_questions(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    if material.group.created_by_id != current_user.id:
        flash('Unauthorized', 'error')
        return redirect(url_for('dashboard'))
    questions = Question.query.filter_by(material_id=material.id).all()
    return render_template('manage_questions.html', material=material, questions=questions)

@app.route('/material/<int:material_id>/add_question', methods=['POST'])
@login_required
def add_question(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    if material.group.created_by_id != current_user.id:
        return redirect(url_for('dashboard'))
        
    question = Question(
        material_id=material.id,
        text=request.form.get('text'),
        option_a=request.form.get('option_a'),
        option_b=request.form.get('option_b'),
        option_c=request.form.get('option_c'),
        option_d=request.form.get('option_d'),
        correct_option=request.form.get('correct_option')
    )
    db.session.add(question)
    db.session.commit()
    return redirect(url_for('manage_questions', material_id=material.id))

@app.route('/study/<int:material_id>')
@login_required
def study_flow(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    # Basic check if user is in group
    # (Simplified for MVP, ideally should check GroupMember)
    
    questions = Question.query.filter_by(material_id=material.id).all()
    
    # Get recent messages
    messages = ChatMessage.query.filter_by(material_id=material.id).order_by(ChatMessage.timestamp.asc()).all()
    
    # Serialize questions for JS
    questions_json = []
    for q in questions:
        questions_json.append({
            'text': q.text,
            'option_a': q.option_a,
            'option_b': q.option_b,
            'option_c': q.option_c,
            'option_d': q.option_d,
            'correct_option': q.correct_option
        })
    
    return render_template('study_flow.html', material=material, questions_json=questions_json, messages=messages)

@app.route('/study/<int:material_id>/submit', methods=['POST'])
@login_required
def submit_score(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    score = int(request.form.get('score'))
    max_score = len(material.questions)
    
    # Check if attempting again? For now, allow multiple, or just update.
    # Let's save a new attempt.
    attempt = QuizAttempt(
        user_id=current_user.id,
        material_id=material.id,
        score=score,
        max_score=max_score
    )
    db.session.add(attempt)
    db.session.commit()
    return redirect(url_for('leaderboard', material_id=material.id))

@app.route('/leaderboard/<int:material_id>')
@login_required
def leaderboard(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    # Get all attempts, order by score desc
    attempts = QuizAttempt.query.filter_by(material_id=material.id).order_by(QuizAttempt.score.desc()).all()
    
    # Filter unique best score per user if desired, or just show all
    # Let's show all for simplicity of MVP
    
    return render_template('leaderboard.html', material=material, attempts=attempts)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    # emit('message', {'username': 'System', 'msg': username + ' has entered the room.'}, room=room)

@socketio.on('message')
def handle_message(data):
    room = data['room']
    content = data['msg']
    user_id = current_user.id
    material_id = int(room.split('_')[1])
    
    # Save to DB
    msg = ChatMessage(content=content, user_id=user_id, material_id=material_id)
    db.session.add(msg)
    db.session.commit()
    
    emit('message', {'username': current_user.username, 'msg': content}, room=room)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
