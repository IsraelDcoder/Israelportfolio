from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import sqlite3
import requests
from datetime import datetime
import logging
import smtplib, ssl
from email.message import EmailMessage

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables with debugging
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path, override=True)
logging.info(f"Loading .env from: {env_path}")
logging.info(f"OPENROUTER_API_KEY present: {bool(os.getenv('OPENROUTER_API_KEY'))}")

app = Flask(__name__, template_folder='template', static_folder='static')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key')

def get_db_connection():
    # Use SQLITE_PATH from .env if set, otherwise default to database.db in project
    db_path = os.getenv('SQLITE_PATH', 'database.db')
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # SQLite types and autoincrement primary key
    cur.execute('''
        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            excerpt TEXT,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute("SELECT COUNT(*) FROM blog_posts")
    result = cur.fetchone()
    count = result[0] if result else 0

    if count == 0:
        sample_posts = [
            {
                'title': 'Building AI-Powered SaaS: Lessons from LaunchLens',
                'slug': 'building-ai-powered-saas-launchlens',
                'excerpt': 'How we built an AI analytics platform that tracks and optimizes startup launches across Product Hunt and X.',
                'content': 'Building LaunchLens taught me invaluable lessons about combining AI with real-world business needs...',
                'category': 'AI & SaaS'
            },
            {
                'title': 'The KRAITIN Mission: Empowering Millions Through Technology',
                'slug': 'kraitin-mission-empowering-millions',
                'excerpt': 'My journey building a tech ecosystem designed to democratize technology and empower communities.',
                'content': 'KRAITIN represents more than just a company - it is a movement to make technology accessible to everyone...',
                'category': 'Innovation'
            },
            {
                'title': 'Full-Stack Development in 2025: My Tech Stack',
                'slug': 'full-stack-development-2025-tech-stack',
                'excerpt': 'A deep dive into the modern tools and frameworks I use to build enterprise-grade applications.',
                'content': 'After 7 years of coding, here is the tech stack that helps me build scalable, production-ready applications...',
                'category': 'Development'
            }
        ]
        
        for post in sample_posts:
            cur.execute(
                'INSERT INTO blog_posts (title, slug, excerpt, content, category) VALUES (?, ?, ?, ?, ?)',
                (post['title'], post['slug'], post['excerpt'], post['content'], post['category'])
            )
    
    conn.commit()
    cur.close()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/projects')
def projects():
    return render_template('projects.html')

@app.route('/startup')
def startup():
    return render_template('startup.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Support JSON and form data (e.g., from HTML forms)
        data = request.get_json(silent=True) or request.form or {}
        name = data.get('name')
        sender_email = data.get('email')
        subject = data.get('subject', '')
        message = data.get('message')
        
        # Validate required fields
        if not name or not sender_email or not message:
            return jsonify({'success': False, 'error': 'Missing required fields (name, email, message)'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO contact_messages (name, email, subject, message) VALUES (?, ?, ?, ?)',
            (name, sender_email, subject, message)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        # Try to send email notification (if SMTP configured)
        recipient = os.getenv('CONTACT_RECIPIENT', 'theonyekachithompson@gmail.com')
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '465'))
        smtp_user = os.getenv('SMTP_USERNAME')
        smtp_pass = os.getenv('SMTP_PASSWORD')

        email_sent = False
        email_error = None

        if smtp_user and smtp_pass:
            try:
                msg = EmailMessage()
                msg['Subject'] = f'New contact message: {subject or "(no subject)"}'
                msg['From'] = smtp_user
                msg['To'] = recipient
                msg.set_content(f"""You have a new message from your website contact form:

Name: {name}
Email: {sender_email}
Subject: {subject}
Message:
{message}

Submitted at: {datetime.utcnow().isoformat()} UTC
""")

                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                email_sent = True
            except Exception as e:
                logging.exception('Failed to send contact email')
                email_error = str(e)
        else:
            logging.warning('SMTP credentials not configured; skipping sending email.')

        return jsonify({'success': True, 'message': 'Message saved.', 'email_sent': email_sent, 'email_error': email_error})
    
    return render_template('contact.html')

@app.route('/api/blog')
def blog_api():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, title, slug, excerpt, category, created_at FROM blog_posts ORDER BY created_at DESC')
    posts = cur.fetchall()
    cur.close()
    conn.close()

    blog_posts = []
    for post in posts:
        # created_at in SQLite comes back as string; try to parse it, otherwise use as-is
        created_at_val = post['created_at'] if isinstance(post, sqlite3.Row) else post[5]
        formatted_date = None
        if isinstance(created_at_val, str):
            try:
                dt = datetime.fromisoformat(created_at_val)
                formatted_date = dt.strftime('%B %d, %Y')
            except Exception:
                # fallback: try common SQLite datetime format
                try:
                    dt = datetime.strptime(created_at_val, '%Y-%m-%d %H:%M:%S')
                    formatted_date = dt.strftime('%B %d, %Y')
                except Exception:
                    formatted_date = created_at_val
        elif isinstance(created_at_val, datetime):
            formatted_date = created_at_val.strftime('%B %d, %Y')
        else:
            formatted_date = str(created_at_val)

        blog_posts.append({
            'id': post['id'] if isinstance(post, sqlite3.Row) else post[0],
            'title': post['title'] if isinstance(post, sqlite3.Row) else post[1],
            'slug': post['slug'] if isinstance(post, sqlite3.Row) else post[2],
            'excerpt': post['excerpt'] if isinstance(post, sqlite3.Row) else post[3],
            'category': post['category'] if isinstance(post, sqlite3.Row) else post[4],
            'created_at': formatted_date
        })
    
    return jsonify(blog_posts)

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    # Reload environment variables on each request (during development)
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path, override=True)
    
    api_key = os.getenv('OPENROUTER_API_KEY')
    logging.info(f"API Key length: {len(api_key) if api_key else 'None'}")
    
    if not api_key:
        env_vars = {k: (v[:5] + '...' if 'key' in k.lower() else v) for k, v in os.environ.items()}
        logging.error(f"Environment variables: {env_vars}")
        return jsonify({'error': 'OpenRouter API key not configured. Please check your .env file.'}), 500
    
    data = request.get_json()
    user_message = data.get('message', '')
    
    system_prompt = """You are an AI assistant representing Israel Thompson, a full-stack developer, AI builder, and founder of KRAITIN and LaunchLens. 

About Israel:
- Almost 7 years of coding experience (since 2018)
- Full-stack developer specializing in enterprise-grade SaaS products
- Founder of KRAITIN: a tech ecosystem built to empower millions through technology
- Founder of LaunchLens: an AI-powered startup analytics platform that tracks and optimizes product launches across Product Hunt, X (Twitter), and other platforms
- Created other products: Summafy (AI summarization tool), Inpublic.ai (AI public opinion summarizer), KraitinForge (portfolio generator), and Edu to Earn (educational rewards platform)
- Mission-driven developer passionate about empowering people through technology, AI, and education
- Tech stack includes: React, Next.js, Node.js, Flask, PostgreSQL, Redis, TypeScript, Python, AI/ML tools

Answer questions about Israel, his projects, experience, and expertise in a professional and friendly manner. Keep responses concise and helpful."""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",  # Using Mistral, a reliable open model
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 300,
                "temperature": 0.7
            }
        )
        
        result = {}
        try:
            result = response.json()
        except ValueError:
            logging.error("Failed to parse JSON response from OpenRouter")
            logging.error(f"Raw response: {response.text}")
        
        if response.status_code == 200 and isinstance(result, dict) and 'choices' in result and len(result['choices']) > 0:
            choice = result['choices'][0]
            # Support multiple response formats
            if isinstance(choice.get('message'), dict) and 'content' in choice['message']:
                bot_response = choice['message']['content']
            elif 'text' in choice:
                bot_response = choice['text']
            else:
                bot_response = str(choice)
            return jsonify({'response': bot_response})
        else:
            logging.error(f"OpenRouter API error: status={response.status_code}, body={response.text}")
            return jsonify({'error': 'OpenRouter API error', 'details': result}), 500
    except Exception as e:
        logging.exception("Exception occurred when calling OpenRouter")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

def init_app():
    with app.app_context():
        init_db()

# Initialize database when the app is created
init_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
