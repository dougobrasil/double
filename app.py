from flask import Flask, render_template_string, request, session, redirect, url_for, send_file, jsonify
from flask_socketio import SocketIO
from werkzeug.security import check_password_hash
import requests
import threading
import time
import sqlite3
import uuid
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "CHAVE_DOUGO_V15_BATCH_SYSTEM" 
socketio = SocketIO(app, cors_allowed_origins="*")

DB_NAME = "usuarios_bot.db"
URL_API = "http://127.0.0.1:8000/api"

# --- CONFIGURAÇÃO DB ---
def init_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # Tabela de Usuários (Agora com duration_minutes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    expiration_date DATETIME,
                    session_token TEXT,
                    duration_minutes INTEGER
                )
            ''')
            
            # Migrações para garantir compatibilidade com versões antigas
            try: cursor.execute("ALTER TABLE users ADD COLUMN session_token TEXT")
            except: pass 
            
            try: cursor.execute("ALTER TABLE users ADD COLUMN duration_minutes INTEGER")
            except: pass 
            
            # Configurações
            cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT UNIQUE NOT NULL, value TEXT NOT NULL)''')
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'false')")
            
            conn.commit()
    except Exception as e:
        print(f"Erro DB: {e}")

init_db()

# --- HELPERS ---
def parse_db_date(date_str):
    if not date_str: return None
    try: return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except: 
        try: return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except: return datetime(2000, 1, 1) # Data expirada se falhar

def is_maintenance_active():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='maintenance'")
            row = cursor.fetchone()
            return row and row[0] == 'true'
    except: return False

# --- LÓGICA DO BOT ---
estado = {
    "placar": {"green": 0, "red": 0, "branco": 0},
    "ultimo_id": None,
    "historico": [],
    "sinal": None,
    "padrao": None,
    "gale": 0
}

def analisar_estrategias(cores, rolls):
    if len(cores) < 10: return None, None
    if rolls[0] in [8, 11] and cores[0] == 2: return "PUXA PRETO", 2
    if rolls[0] in [1, 5] and cores[0] == 1: return "PUXA VERMELHO", 1
    if cores[0] == cores[1] == cores[2] == cores[3] and cores[0] != 0:
        return "QUEBRA DE SURF", (2 if cores[0] == 1 else 1)
    if cores[0] != cores[1] and cores[0] == cores[2] and cores[1] == cores[3]:
        return "XADREZ", (1 if cores[0] == 2 else 2)
    if cores[1] == 0:
        return "VIZINHO DO BRANCO", (2 if cores[0] == 1 else 1)
    return None, None

def bot_worker():
    global estado
    while True:
        try:
            manutencao = is_maintenance_active()
            response = requests.get(URL_API, timeout=5).json()
            if response and "items" in response:
                itens = response["items"]
                cores = [i["color"] for i in itens]
                rolls = [i["roll"] for i in itens]
                atual_id = itens[0]["id"]

                if atual_id != estado["ultimo_id"]:
                    cor_vitoria = cores[0]
                    if estado["sinal"] is not None:
                        if cor_vitoria == estado["sinal"] or cor_vitoria == 0:
                            estado["placar"]["green"] += 1
                            if cor_vitoria == 0: estado["placar"]["branco"] += 1
                            estado["sinal"] = None
                            estado["gale"] = 0
                        else:
                            if estado["gale"] < 2: 
                                estado["gale"] += 1
                            else:
                                estado["placar"]["red"] += 1
                                estado["sinal"] = None
                                estado["gale"] = 0
                    
                    estado["ultimo_id"] = atual_id
                    estado["historico"] = itens[:10]

                    if estado["sinal"] is None:
                        msg, sug = analisar_estrategias(cores, rolls)
                        if msg:
                            estado["sinal"] = sug
                            estado["padrao"] = msg

                socketio.emit('update', {
                    'placar': estado['placar'],
                    'historico': estado['historico'],
                    'sinal': "VERMELHO" if estado['sinal'] == 1 else ("PRETO" if estado['sinal'] == 2 else None),
                    'padrao': estado['padrao'],
                    'gale': estado['gale'],
                    'manutencao': manutencao
                })
        except: pass
        time.sleep(2)

def verificar_acesso_interno():
    if not session.get('logged_in'): return False, "Faça login."
    
    username = session.get('username')
    token_browser = session.get('token')
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT expiration_date, session_token FROM users WHERE username = ?", (username,))
            data = cursor.fetchone()
            
            if not data: return False, "Conta removida."
            
            # Se expiration_date for None, significa que o usuario ainda nao logou a primeira vez
            # Mas se ele está aqui dentro da função verificar_acesso_interno, ele deveria ter passado pelo login.
            # Caso raro de inconsistencia, tratamos como erro ou deixamos passar se tiver duração
            if data[0] is None:
                return True, datetime.now().isoformat() # Retorna agora para nao travar o timer

            exp_date = parse_db_date(data[0])
            token_db = data[1]
            
            if datetime.now() > exp_date: return False, "Tempo esgotado."
            if token_browser != token_db: return False, "Desconectado (Outro dispositivo)."
            
            return True, exp_date.isoformat()
    except: return False, "Erro sistema."

# --- HTML TEMPLATES ---

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acesso Restrito</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
        body { background-color: #000; display: flex; justify-content: center; align-items: center; min-height: 100vh; color: #fff; overflow: hidden; }
        .login-wrapper { width: 100%; max-width: 400px; padding: 20px; text-align: center; position: relative; z-index: 10; }
        .logo-container { position: relative; margin-bottom: 40px; display: inline-block; }
        .logo-img { width: 150px; height: auto; position: relative; z-index: 2; filter: drop-shadow(0 0 15px rgba(255, 0, 0, 0.6)); }
        .glow-effect { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 160px; height: 160px; background: radial-gradient(circle, rgba(255,0,0,0.4) 0%, rgba(0,0,0,0) 70%); z-index: 1; border-radius: 50%; }
        form { display: flex; flex-direction: column; gap: 15px; }
        .input-group { position: relative; }
        .input-group i { position: absolute; left: 20px; top: 50%; transform: translateY(-50%); color: #666; font-size: 14px; }
        input { width: 100%; padding: 15px 15px 15px 45px; background-color: #121212; border: 1px solid #333; border-radius: 30px; color: #fff; font-size: 14px; outline: none; transition: 0.3s; }
        input:focus { border-color: #ff0000; box-shadow: 0 0 10px rgba(255, 0, 0, 0.2); }
        .btn-login { background-color: #ff0000; color: #000; border: none; padding: 15px; border-radius: 30px; font-weight: bold; font-size: 16px; cursor: pointer; margin-top: 10px; transition: transform 0.2s, box-shadow 0.2s; text-transform: uppercase; }
        .btn-login:hover { transform: scale(1.02); box-shadow: 0 0 20px rgba(255, 0, 0, 0.4); background-color: #ff1a1a; }
        .divider { margin: 30px 0 20px 0; border-top: 1px solid #222; }
        .footer-text { color: #fff; font-size: 14px; margin-bottom: 15px; }
        .btn-whatsapp { background-color: #25D366; color: white; text-decoration: none; padding: 12px 25px; border-radius: 30px; font-weight: bold; display: inline-flex; align-items: center; gap: 10px; font-size: 14px; transition: 0.3s; }
        .btn-whatsapp:hover { background-color: #1ebc57; transform: scale(1.05); }
        .error-msg { color: #ff3333; font-size: 13px; margin-top: 10px; background: rgba(255,0,0,0.1); padding: 10px; border-radius: 10px; border: 1px solid rgba(255,0,0,0.2); animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="login-wrapper">
        <div class="logo-container">
            <div class="glow-effect"></div>
            <img src="/logo_img" alt="Area 51" class="logo-img">
        </div>
        <form method="POST" action="{{ url_for('login') }}">
            <div class="input-group">
                <i class="fas fa-user"></i>
                <input type="text" name="username" placeholder="Usuário" required autocomplete="off">
            </div>
            <div class="input-group">
                <i class="fas fa-lock"></i>
                <input type="password" name="password" placeholder="Senha" required>
            </div>
            <button type="submit" class="btn-login">Entrar</button>
        </form>
        {% if error %}
            <div class="error-msg"><i class="fas fa-exclamation-triangle"></i> {{ error }}</div>
        {% endif %}
        <div class="divider"></div>
        <div class="footer-text">Quer comprar ou renovar seu acesso?</div>
        <a href="https://wa.me/5500000000000" target="_blank" class="btn-whatsapp"><i class="fab fa-whatsapp"></i> Fale Conosco</a>
    </div>
</body>
</html>
"""

HTML_INDEX = """
<!DOCTYPE html>
<html>
<head>
    <title>DOUGO BRASIL - V15</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        body { background: #000; color: #fff; font-family: 'Rajdhani', sans-serif; text-align: center; margin: 0; padding-bottom: 20px; background-image: radial-gradient(circle at top, #1a0000 0%, #000000 70%); }
        .header { display: flex; justify-content: space-between; padding: 15px 20px; background: rgba(10, 10, 10, 0.9); border-bottom: 1px solid #333; align-items: center; }
        .user-info { display: flex; flex-direction: column; align-items: flex-start; }
        .timer-box { font-size: 14px; color: #ff3333; font-weight: bold; }
        .logout-btn { background: #222; color: #ff3333; border: 1px solid #ff3333; text-decoration: none; padding: 5px 15px; border-radius: 4px; font-size: 14px; font-weight: bold; transition: 0.3s; }
        .logout-btn:hover { background: #ff3333; color: black; }
        .container { max-width: 800px; margin: auto; padding: 20px; }
        .placar { display: flex; justify-content: space-around; background: #0a0a0a; padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 1px solid #222; }
        .stat-value { font-size: 32px; font-weight: bold; }
        .green { color: #00ff66; text-shadow: 0 0 10px rgba(0,255,100,0.3); } 
        .red { color: #ff3333; text-shadow: 0 0 10px rgba(255,50,50,0.3); } 
        .white { color: #ffffff; text-shadow: 0 0 10px rgba(255,255,255,0.3); }
        .historico-bar { background: #0a0a0a; border: 1px solid #222; padding: 10px; border-radius: 8px; min-height: 50px; display: flex; justify-content: center; flex-wrap: wrap; gap: 5px; }
        .ball { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 8px; font-weight: bold; font-size: 18px; }
        .c1 { background: #d32f2f; color: white; } 
        .c2 { background: #212121; color: white; border: 1px solid #444; } 
        .c0 { background: white; color: black; }
        .sinal-card { background: #0a0a0a; border: 1px solid #222; padding: 30px; border-radius: 15px; margin-top: 20px; transition: 0.3s; }
        .ativo { border-color: #00ff66; box-shadow: 0 0 30px rgba(0, 255, 100, 0.1); }
        .manutencao { border-color: #ffaa00; box-shadow: 0 0 20px rgba(255, 170, 0, 0.2); }
    </style>
</head>
<body>
    <div class="header">
        <div class="user-info">
            <span style="font-size: 16px; color: #ccc;">User: <b>{{ user }}</b></span>
            <span id="timer" class="timer-box">...</span>
        </div>
        <a href="/logout" class="logout-btn">SAIR</a>
    </div>
    <div class="container">
        <img src="/logo_img" style="width: 80px; opacity: 0.8; margin-bottom: 10px;">
        <h1 style="margin: 0 0 20px 0; color: #ff3333;">AREA 51 V15</h1>
        <div class="placar">
            <div><div class="green" style="font-size: 14px;">WIN</div><div id="g" class="stat-value green">0</div></div>
            <div><div class="red" style="font-size: 14px;">LOSS</div><div id="r" class="stat-value red">0</div></div>
            <div><div class="white" style="font-size: 14px;">BRANCO</div><div id="b" class="stat-value white">0</div></div>
        </div>
        <h3 style="color: #666; font-size: 12px;">ÚLTIMOS RESULTADOS</h3>
        <div id="hist" class="historico-bar"></div>
        <div id="sinal-box" class="sinal-card">
            <h2 id="status-txt" style="color: #666; margin: 0;">AGUARDANDO...</h2>
            <div id="detalhes" style="color: #888; margin-top: 15px;">Analisando fluxo...</div>
        </div>
    </div>
    <script>
        const expirationDate = new Date("{{ expiration_date }}");
        
        function updateTimer() {
            const now = new Date();
            const diff = expirationDate - now;
            if (diff <= 0) {
                window.location.href = "/logout?msg=Seu tempo de acesso acabou!"; 
                return; 
            }
            const d = Math.floor(diff / (1000 * 60 * 60 * 24));
            const h = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const s = Math.floor((diff % (1000 * 60)) / 1000);
            document.getElementById("timer").innerText = `EXP: ${d}d ${h}h ${m}m ${s}s`;
        }
        setInterval(updateTimer, 1000); updateTimer();

        setInterval(function() {
            fetch('/check_status')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'invalid') {
                        window.location.href = "/logout?msg=" + encodeURIComponent(data.reason);
                    }
                });
        }, 5000);

        var socket = io();
        socket.on('update', function(data) {
            document.getElementById('g').innerText = data.placar.green;
            document.getElementById('r').innerText = data.placar.red;
            document.getElementById('b').innerText = data.placar.branco;
            
            let histHtml = '';
            if(data.historico) data.historico.forEach(item => histHtml += `<div class="ball c${item.color}">${item.roll}</div>`);
            document.getElementById('hist').innerHTML = histHtml;
            
            let box = document.getElementById('sinal-box');
            let statusTxt = document.getElementById('status-txt');
            let detalhes = document.getElementById('detalhes');

            if(data.manutencao) {
                box.className = 'sinal-card manutencao';
                statusTxt.innerHTML = "⚠️ SISTEMA EM MANUTENÇÃO";
                statusTxt.style.color = "#ffaa00";
                detalhes.innerHTML = "As análises foram pausadas pelo administrador.";
                return;
            }

            if(data.sinal) {
                box.className = 'sinal-card ativo';
                let corStyle = data.sinal == 'VERMELHO' ? 'color:#ff3333' : (data.sinal == 'PRETO' ? 'color:white' : 'color:#00ff66');
                statusTxt.innerHTML = "ENTRADA CONFIRMADA";
                statusTxt.style.color = "#00ff66";
                detalhes.innerHTML = `<div style="font-size: 40px; font-weight: bold; margin: 15px 0; ${corStyle};">${data.sinal}</div><div style="color: #ccc;">${data.padrao} • ${data.gale == 0 ? "TIRO SECO" : "GALE " + data.gale}</div>`;
            } else {
                box.className = 'sinal-card';
                statusTxt.innerText = "AGUARDANDO...";
                statusTxt.style.color = "#666";
                detalhes.innerHTML = "Analisando fluxo...";
            }
        });
    </script>
</body>
</html>
"""

# --- ROTAS FLASK ---
@app.route('/check_status')
def check_status():
    valido, msg = verificar_acesso_interno()
    if not valido: return jsonify({"status": "invalid", "reason": msg})
    return jsonify({"status": "ok"})

@app.route('/logo_img')
def serve_logo():
    if os.path.exists('area51.png'): return send_file('area51.png', mimetype='image/png')
    return "", 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = request.args.get('error')
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash, expiration_date, duration_minutes FROM users WHERE username = ?", (username,))
                user_data = cursor.fetchone()
                
                if user_data:
                    stored_pw = user_data[0]
                    exp_date_raw = user_data[1]
                    duration = user_data[2]
                    
                    if check_password_hash(stored_pw, password):
                        # --- LÓGICA DE PRIMEIRO ACESSO ---
                        # Se expiration_date for NULL, significa que é o primeiro login.
                        if exp_date_raw is None:
                            if duration is None: duration = 60 # Fallback 1h
                            
                            nova_data = datetime.now() + timedelta(minutes=duration)
                            
                            # Salva a data definitiva no banco
                            cursor.execute("UPDATE users SET expiration_date = ? WHERE username = ?", (nova_data, username))
                            conn.commit()
                            
                            exp_date = nova_data # Atualiza variável local
                        else:
                            exp_date = parse_db_date(exp_date_raw)
                        
                        # Verifica se expirou (agora que temos data certa)
                        if datetime.now() < exp_date:
                            novo_token = str(uuid.uuid4())
                            cursor.execute("UPDATE users SET session_token = ? WHERE username = ?", (novo_token, username))
                            conn.commit()
                            session['logged_in'] = True
                            session['username'] = username
                            session['token'] = novo_token
                            return redirect(url_for('index'))
                        else: error = "Seu tempo de acesso expirou."
                    else: error = "Senha incorreta."
                else: error = "Usuário não encontrado."
        except Exception as e: error = f"Erro Interno: {e}"
    return render_template_string(HTML_LOGIN, error=error)

@app.route('/logout')
def logout():
    msg = request.args.get('msg') 
    session.clear()
    if msg: return redirect(url_for('login', error=msg))
    return redirect(url_for('login'))

@app.route('/')
def index():
    valido, resultado = verificar_acesso_interno()
    if not valido: 
        session.clear()
        return redirect(url_for('login', error=resultado))
    return render_template_string(HTML_INDEX, user=session.get('username'), expiration_date=resultado)

if __name__ == '__main__':
    threading.Thread(target=bot_worker, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
