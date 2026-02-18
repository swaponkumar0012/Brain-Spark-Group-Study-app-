from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_teacher = db.Column(db.Boolean, default=False)
    
    # Relationships
    groups_created = db.relationship('Group', backref='creator', lazy=True)
    # For simplicity, using a simple join table or logic for memberships would be better, 
    # but let's stick to basics. 
    # A user can be a member of many groups
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    members = db.relationship('GroupMember', backref='group', lazy=True)
    materials = db.relationship('StudyMaterial', backref='group', cascade='all, delete-orphan', lazy=True)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)

class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    pdf_filename = db.Column(db.String(300), nullable=False) # Store path or filename
    
    reading_time_seconds = db.Column(db.Integer, default=60)
    quiz_time_seconds = db.Column(db.Integer, default=60)
    
    questions = db.relationship('Question', backref='material', cascade='all, delete-orphan', lazy=True)
    attempts = db.relationship('QuizAttempt', backref='material', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', or 'D'

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    
    user = db.relationship('User', backref='messages')
    material = db.relationship('StudyMaterial', backref='messages')
