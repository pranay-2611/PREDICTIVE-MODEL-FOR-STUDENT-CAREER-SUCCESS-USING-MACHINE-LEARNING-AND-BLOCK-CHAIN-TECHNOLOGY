import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import json
import joblib
import pandas as pd
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

with open("contract_info.json", "r") as f:
    info = json.load(f)
contract = w3.eth.contract(address=info['address'], abi=info['abi'])

artifacts = joblib.load('model/student_placement_model.pkl')
model = artifacts['model']
trained_cols = artifacts['features']

app = Flask(__name__)
app.secret_key = 'unmyeong'

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            phone_number TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            user_input TEXT NOT NULL,
            data_hash TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            prediction TEXT NOT NULL,
            confidence REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone_number = request.form['phone_number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        conn = get_db_connection()
        user_check = conn.execute(
            'SELECT * FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()

        if user_check:
            flash('Username or email already exists. Please choose a different one.', 'error')
            conn.close()
            return render_template('register.html')
        hashed_password = generate_password_hash(password)

        try:
            conn.execute(
                'INSERT INTO users (username, email, phone_number, password) VALUES (?, ?, ?, ?)',
                (username, email, phone_number, hashed_password)
            )
            conn.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('An error occurred during registration. Please try again.', 'error')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/home')
def home():
    if 'username' not in session:
        flash('Please log in to access the home page.', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute(
        'SELECT username, email, phone_number FROM users WHERE username = ?',
        (session['username'],)
    ).fetchone()
    conn.close()

    return render_template('home.html', user=user)

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if 'username' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()
            
            df_input = pd.DataFrame([form_data])
            
            numeric_cols = [
                'Age', 'Average GPA', 'Backlogs', 'Attendance (%)', 
                'Sem1 GPA', 'Sem2 GPA', 'Sem3 GPA', 'Sem4 GPA', 
                'Sem5 GPA', 'Sem6 GPA', 'Sem7 GPA', 'Sem8 GPA'
            ]
            for col in numeric_cols:
                df_input[col] = pd.to_numeric(df_input[col], errors='coerce')
            
            df_input['Skill_Count'] = df_input['Skills'].apply(lambda x: len(str(x).split(',')) if x else 0)
            df_input['Club_Count'] = df_input['Clubs'].apply(lambda x: len(str(x).split(',')) if x else 0)
            df_input['GPA_Trend'] = df_input['Sem8 GPA'] - df_input['Sem1 GPA']
            
            df_input['Gender'] = df_input['Gender'].map({'Male': 1, 'Female': 0}).fillna(0)
            df_input['Internship Done'] = df_input['Internship Done'].map({'Yes': 1, 'No': 0}).fillna(0)
            
            df_input = pd.get_dummies(df_input, columns=['Branch', 'Internship Domain'])
            
            for col in trained_cols:
                if col not in df_input.columns:
                    df_input[col] = 0
            df_final = df_input[trained_cols]

            prediction_idx = model.predict(df_final)[0]
            confidence = model.predict_proba(df_final)[0][1]
            result_text = "Placed" if prediction_idx == 1 else "Not Placed"
            final_conf = round(float(confidence * 100), 2)

            input_string_for_hash = f"{session['username']}-{json.dumps(form_data, sort_keys=True)}"
            data_hash = hashlib.sha256(input_string_for_hash.encode()).hexdigest()

            tx_hash = contract.functions.storeRecord(
                session['username'], 
                data_hash, 
                result_text
            ).transact({'from': w3.eth.accounts[0]})
            
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            blockchain_tx_id = tx_receipt.transactionHash.hex()

            conn = get_db_connection()
            conn.execute('''
                INSERT INTO prediction_history 
                (username, user_input, data_hash, transaction_id, prediction, confidence) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session['username'], 
                json.dumps(form_data), 
                data_hash, 
                blockchain_tx_id, 
                result_text, 
                final_conf
            ))
            conn.commit()
            conn.close()

            return render_template('predict.html', 
                                   prediction=result_text, 
                                   confidence=final_conf,
                                   tx_id=blockchain_tx_id,
                                   data_hash=data_hash)

        except Exception as e:
            flash(f"System Error: {str(e)}", "error")
            return redirect(url_for('predict'))

    return render_template('predict.html')

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_history = conn.execute(
        'SELECT * FROM prediction_history WHERE username = ? ORDER BY timestamp DESC',
        (session['username'],)
    ).fetchall()
    conn.close()

    return render_template('history.html', history=user_history)

@app.route('/analytics')
def analytics():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    query = '''
        SELECT prediction, COUNT(*) as count 
        FROM prediction_history 
        WHERE username = ? 
        GROUP BY prediction
    '''
    results = conn.execute(query, (session['username'],)).fetchall()
    conn.close()

    labels = []
    values = []
    
    for row in results:
        labels.append(row['prediction'])
        values.append(row['count'])

    return render_template('analytics.html', labels=json.dumps(labels), values=json.dumps(values))

@app.route('/datascience')
def datascience():
    return render_template('datascience.html')

@app.route('/proposed')
def proposed():
    return render_template('proposed.html')

if __name__ == '__main__':
    app.run(debug=True)
