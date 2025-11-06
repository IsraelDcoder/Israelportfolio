from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import psycopg2
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SESSION_SECRET', 'dev-secret-key')

def get_db_connection():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS blog_posts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            slug VARCHAR(255) UNIQUE NOT NULL,
            excerpt TEXT,
            content TEXT NOT NULL,
            category VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS contact_messages (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            subject VARCHAR(255),
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
                'INSERT INTO blog_posts (title, slug, excerpt, content, category) VALUES (%s, %s, %s, %s, %s)',
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
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        subject = data.get('subject', '')
        message = data.get('message')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO contact_messages (name, email, subject, message) VALUES (%s, %s, %s, %s)',
            (name, email, subject, message)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Message sent successfully!'})
    
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
        blog_posts.append({
            'id': post[0],
            'title': post[1],
            'slug': post[2],
            'excerpt': post[3],
            'category': post[4],
            'created_at': post[5].strftime('%B %d, %Y')
        })
    
    return jsonify(blog_posts)

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        return jsonify({'error': 'OpenRouter API key not configured. Please add OPENROUTER_API_KEY to your environment variables.'}), 500
    
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
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 300,
                "temperature": 0.7
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_response = result['choices'][0]['message']['content']
            return jsonify({'response': bot_response})
        else:
            return jsonify({'error': f'API error: {response.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
