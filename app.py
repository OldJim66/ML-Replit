#------ Import Python Libraries ----------
import os
import time
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
os.environ['BASE_DIR'] = BASE_DIR
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from static.py import RecSQL
from static.py.JMC_Func import string_to_bool as S2B
from static.py.JMC_Func import ClientResponses
from static.py.LogConf import log
import secrets
from flask_socketio import SocketIO
import sqlalchemy
import traceback
#------ Import Python Libraries End ----------

#------App Config Start ----------
try:
    app = Flask(__name__)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # or 'None' if you need cross-site cookies
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(16))
    socketio = SocketIO(app)
except Exception as e:
         log.error(f"Error initializing the Flask app and login manager:\n{e}")

try:
    load_dotenv()
except Exception as e:
        log.error(f"Error loading environment variables from .env file:\n{e}")
#------App Config End ----------

#------DB Setup Start ----------
try:
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db_path = os.path.join(BASE_DIR, 'DB', 'ml.db')
    os.makedirs(os.path.join(BASE_DIR, 'DB'), exist_ok=True)
except Exception as e:
     log.error(f"Error configuring the Flask app and creating the database directory:\n{e}")

try:
    sql_type = os.getenv('SQL', 'SQLite')
    if sql_type == 'SQLite':
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    elif sql_type == 'MySQL':
        user = os.getenv('MySQL_User')
        password = os.getenv('MySQL_Pass')
        host = os.getenv('MySQL_Host')
        dbname = os.getenv('MySQL_DBName')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{user}:{password}@{host}/{dbname}'
except Exception as e:
    log.error(f"Error configuring the SQLAlchemy database URI:\n{e}")

try:
    db = SQLAlchemy(app)
except Exception as e:
    log.error(f"Error initializing SQLAlchemy with the Flask app:\n{e}")

try:
    class BaseModel(db.Model):
        __abstract__ = True

        @classmethod
        def get_class_by_tablename(cls, tablename):
            for c in cls.registry.mappers:
                if c.class_.__tablename__ == tablename:
                    return c.class_
            return None
except Exception as e:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while getting the class by table name")

try:
    class User(BaseModel, UserMixin):
        __tablename__ = 'user'

        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True, nullable=False)
        password = db.Column(db.String(255), nullable=False)

        def __repr__(self):
            return f'<User {self.id}>'
except Exception as e:
    log.error(f"Error defining the User model:\n{e}")

try:
    with app.app_context():
        db.create_all()
        if sql_type == 'SQLite':
            with db.engine.connect() as connection:
                connection.execute(sqlalchemy.text('PRAGMA journal_mode=MEMORY'))
        event.listens_for(db.engine, "before_cursor_execute")(RecSQL.before_cursor_execute)
except Exception as e:
        log.error(f"Error creating database tables and setting up event listener:\n{e}")
#------DB Setup End ----------
    
#------Base Routes Start ----------    
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(os.path.join(app.root_path, 'static'), 
                                   'LogoJMC.ico', mimetype='image/vnd.microsoft.icon')
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while serving favicon", 500


@app.route('/')
@app.route('/home')
def home():
    try:
        return render_template('index.html')
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while rendering the home page", 500
#------Base Routes End ----------

#------Authentication / UserManagement Routes Start ----------
@login_manager.user_loader
def load_user(user_id):
    try: 
        return RecSQL.Check(lambda: User.query.with_for_update().get(int(user_id)),db,socketio, BaseModel)
    except Exception as e:
        log.error(f"Error in load_user function:\n{e}")
        return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            existing_user = RecSQL.Check(lambda: User.query.filter_by(username=request.form['username']).first(),db,socketio, BaseModel)
            if existing_user:
                flash('Username already exists', 'warning')  
                return render_template('register.html')
            hashed_password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
            new_user = User(username=request.form['username'], password=hashed_password)
            RecSQL.Check(lambda: db.session.add(new_user),db,socketio, BaseModel)
            flash('Registration successful!', 'success')  
            return redirect(url_for('login'))
        return render_template('register.html')
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while registering", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            user = RecSQL.Check(lambda: User.query.filter_by(username=request.form['username']).first(),db,socketio, BaseModel)
            if user and check_password_hash(user.password, request.form['password']):
                login_user(user)
                session['username'] = request.form['username']
                flash('Welcome, {}!'.format(request.form['username']), 'success')  
                return redirect(url_for('home'))
            flash('Invalid username or password', 'warning')  
        return render_template('login.html')
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while logging in", 500

@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        session.pop('username', None)  
        flash('Logout successful!', 'success')
        return redirect(url_for('home'))
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while logging out", 500
#------Authentication / UserManagement Routes End ----------

#------BrowserMemoryDB Routes Start ----------
@app.route('/BrowserMemoryDB')
def BrowserMemoryDB():
    return render_template('BrowserMemoryDB.html')

@app.route('/set_use_in_memory_db', methods=['POST'])
def set_use_in_memory_db():
    session['use_in_memory_db'] = True
    return '', 204

@app.route('/unset_use_in_memory_db', methods=['POST'])
def unset_use_in_memory_db():
    session['use_in_memory_db'] = False
    return '', 204

@app.route('/get_create_table_sql', methods=['GET', 'POST'])
def get_create_table_sql():
    try:
        Result = RecSQL.GetCreateTableSql(db)
        return jsonify({'sql': str(Result).strip()[2:-2]})
    except Exception:
        log.error(traceback.format_exc())
        return "Error occurred while getting create table sql", 500

@app.route('/ClientResponse', methods=['POST'])
def client_response():
    try:
        data = request.json
        room_id = request.cookies.get('room_id')
        client_responses = ClientResponses()
        client_responses.set_value(room_id, data)      
        return '', 200
    except Exception as e:
        log.error(traceback.format_exc())
        raise RuntimeError("An error occurred while processing the client response")

#------BrowserMemoryDB Routes End ----------

#------Application Setup and Launch Start ----------
try:
    log.info("Environment Settings:"+ 
            "\n Development: " + str(os.getenv('Development'))+ 
            "\n SQL: " + str(os.getenv('SQL')) +
            "\n LOG_LEVEL: " +  str(os.getenv('LOG_LEVEL')) + 
            "\n LOG_2FILE: " + str(os.getenv('LOG_2FILE')) + 
            "\n LOG_OnlyOwn " + str(os.getenv('LOG_OnlyOwn')) + 
            "\n RecSQL: " + str(os.getenv('RecSQL')) + 
            "\n NoCommit: " + str(os.getenv('NoCommit')))
except Exception as e:
    log.error(f"Error logging environment settings:\n{e}")

if __name__ == '__main__':
    try:
        if S2B(os.getenv('Development', False)) == True:
            app.run(debug=True)
    except Exception:
        log.error(traceback.format_exc())       
#------Application Setup and Launch End ----------