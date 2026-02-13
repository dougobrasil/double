import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import os
import sys
import time
import re
import random
import string

# --- PALETA DE CORES (THEME: CLASSIFIED RED) ---
C_RED     = "\033[91m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_BLUE    = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN    = "\033[96m"
C_WHITE   = "\033[97m"
C_GREY    = "\033[90m"
C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"

DB_NAME = "usuarios_bot.db"

# --- UTILITÁRIOS ---
def clear(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def get_db(): 
    return sqlite3.connect(DB_NAME, timeout=10)

def pause(): 
    print(f"\n{C_GREY}  [ PRESSIONE ENTER PARA RETORNAR À BASE ]{C_RESET}")
    input()

def loading(text="PROCESSANDO"):
    print(f"\n  {C_RED}[>>]{C_RESET} {text}", end="")
    for _ in range(3):
        time.sleep(0.15)
        print(".", end="", flush=True)
    print(f" {C_GREEN}OK{C_RESET}")
    time.sleep(0.3)

def len_no_ansi(string):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', string))

def pad_str(text, width):
    visible_len = len_no_ansi(text)
    padding = width - visible_len
    if padding < 0: padding = 0
    return text + " " * padding

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, expiration_date DATETIME, session_token TEXT, duration_minutes INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT UNIQUE NOT NULL, value TEXT NOT NULL)''')
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'false')")
        try: cursor.execute("ALTER TABLE users ADD COLUMN session_token TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN duration_minutes INTEGER")
        except: pass
        conn.commit()

# --- INTERFACE VISUAL ---

def draw_header():
    clear()
    print(f"{C_RED}")
    print(r"   __ _  _ __ ___   __ _      | ___|/ |")
    print(r"  / _` || '__/ _ \ / _` |_____|___ \| |")
    print(r" | (_| || | |  __/| (_| |_____|___) | |")
    print(r"  \__,_||_|  \___| \__,_|     |____/|_|")
    print(f"{C_RESET}")
    print(f"  {C_GREY}:: SISTEMA DE CONTROLE DE ACESSO :: V20 (EXPORT) ::{C_RESET}\n")

def draw_bar(val, total, length=15, color=C_GREEN):
    if total == 0: perc = 0
    else: perc = val / total
    if perc > 1: perc = 1
    
    fill = int(length * perc)
    empty = length - fill
    return f"{color}{'█'*fill}{C_GREY}{'░'*empty}{C_RESET}"

def dashboard():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT expiration_date, session_token FROM users")
        users = cursor.fetchall()
        cursor.execute("SELECT value FROM settings WHERE key='maintenance'")
        row = cursor.fetchone()
        manutencao = row and row[0] == 'true'

    total = len(users)
    now = datetime.now()
    ativos = 0
    vencidos = 0
    pendentes = 0
    online = 0
    
    for u in users:
        if u[0] is None:
            pendentes += 1
            continue
        try: 
            if '.' in u[0]: exp = datetime.strptime(u[0], '%Y-%m-%d %H:%M:%S.%f')
            else: exp = datetime.strptime(u[0], '%Y-%m-%d %H:%M:%S')
        except: continue
        
        if now < exp:
            ativos += 1
            if u[1]: online += 1
        else:
            vencidos += 1
            
    offline = total - online
    bar_ativos = draw_bar(ativos, total, 12, C_GREEN)
    bar_vencidos = draw_bar(vencidos, total, 12, C_RED)
    status_sys = f"{C_YELLOW}EM MANUTENÇÃO{C_RESET}" if manutencao else f"{C_GREEN}ONLINE{C_RESET}"

    print(f"  {C_RED}┌── STATUS GERAL ──────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"  {C_RED}│{C_RESET} SISTEMA: {pad_str(status_sys, 40)} {C_RED}│{C_RESET} {now.strftime('%H:%M')} {C_RED}│{C_RESET}")
    print(f"  {C_RED}├── MÉTRICAS ──────────────────────────────────────────────────────────────┤{C_RESET}")
    print(f"  {C_RED}│{C_RESET} {C_BOLD}TOTAL:{C_RESET}   {pad_str(str(total), 5)}                                                        {C_RED}│{C_RESET}")
    print(f"  {C_RED}│{C_RESET} {C_CYAN}ONLINE:{C_RESET}  {pad_str(str(online), 5)}                 {C_RED}│{C_RESET} {C_WHITE}ATIVOS:{C_RESET}   {pad_str(str(ativos), 4)} {bar_ativos} {C_RED}│{C_RESET}")
    print(f"  {C_RED}│{C_RESET} {C_GREY}OFFLINE:{C_RESET} {pad_str(str(offline), 5)}                 {C_RED}│{C_RESET} {C_WHITE}VENCIDOS:{C_RESET} {pad_str(str(vencidos), 4)} {bar_vencidos} {C_RED}│{C_RESET}")
    print(f"  {C_RED}│{C_RESET}                                {C_RED}│{C_RESET} {C_WHITE}PENDENTE:{C_RESET} {pad_str(f'{C_YELLOW}{pendentes}{C_RESET}', 17)} {C_RED}│{C_RESET}")
    print(f"  {C_RED}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
    print("")

# --- OPERAÇÕES ---

def criar_manual():
    draw_header()
    print(f"  {C_WHITE}>> NOVO ACESSO MANUAL{C_RESET}\n")
    u = input(f"  {C_RED}LOGIN:{C_RESET} ").strip()
    if not u: return
    p = input(f"  {C_RED}SENHA:{C_RESET} ").strip()
    
    print(f"\n  {C_GREY}DURAÇÃO DO ACESSO:{C_RESET}")
    print(f"  {C_WHITE}[1]{C_RESET} HORAS  {C_WHITE}[2]{C_RESET} DIAS  {C_WHITE}[3]{C_RESET} MESES  {C_WHITE}[4]{C_RESET} PERMANENTE")
    op = input(f"  {C_RED}>>{C_RESET} ")
    try: q = int(input(f"  {C_RED}VALOR (Ex: 30):{C_RESET} "))
    except: return

    delta = timedelta(days=1)
    if op=='1': delta = timedelta(hours=q)
    elif op=='2': delta = timedelta(days=q)
    elif op=='3': delta = timedelta(days=q*30)
    elif op=='4': delta = timedelta(days=3650)
    
    exp = datetime.now() + delta
    try:
        with get_db() as conn:
            conn.cursor().execute("INSERT INTO users (username, password_hash, expiration_date) VALUES (?,?,?)", (u, generate_password_hash(p), exp))
            conn.commit()
        loading("REGISTRANDO")
        print(f"\n  {C_GREEN}✔ USUÁRIO CRIADO! EXPIRA EM: {exp.strftime('%d/%m %H:%M')}{C_RESET}")
    except: print(f"\n  {C_RED}✖ ERRO AO CRIAR{C_RESET}")
    pause()

def gerar_lote():
    draw_header()
    print(f"  {C_WHITE}>> GERAÇÃO EM LOTE (REVENDA){C_RESET}\n")
    print(f"  {C_GREY}* O tempo só conta após o 1º login{C_RESET}\n")
    
    prefix = input(f"  {C_RED}PREFIXO (ex: cliente):{C_RESET} ").strip()
    try: qtd = int(input(f"  {C_RED}QUANTIDADE:{C_RESET} "))
    except: return
    
    print(f"\n  {C_GREY}DURAÇÃO DO PACOTE:{C_RESET}")
    print(f"  {C_WHITE}[1]{C_RESET} 1 DIA   {C_WHITE}[2]{C_RESET} 7 DIAS   {C_WHITE}[3]{C_RESET} 30 DIAS   {C_WHITE}[4]{C_RESET} HORAS")
    op = input(f"  {C_RED}>>{C_RESET} ")
    
    mins = 1440
    lbl = "1 DIA"
    if op == '2': mins = 10080; lbl = "7 DIAS"
    elif op == '3': mins = 43200; lbl = "30 DIAS"
    elif op == '4': 
        h = int(input(f"  {C_RED}QUANTAS HORAS?:{C_RESET} "))
        mins = h * 60; lbl = f"{h} HORAS"
        
    loading("GERANDO CHAVES")
    
    lista = []
    with get_db() as conn:
        c = conn.cursor()
        for _ in range(qtd):
            suf = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            user = f"{prefix}_{suf}"
            pw = str(random.randint(100000,999999))
            c.execute("INSERT INTO users (username, password_hash, expiration_date, duration_minutes) VALUES (?,?,NULL,?)", 
                      (user, generate_password_hash(pw), mins))
            lista.append(f"{pad_str(user, 20)} | {pw}")
        conn.commit()
        
    print(f"\n  {C_GREEN}✔ {qtd} CHAVES GERADAS!{C_RESET}\n")
    print(f"  {C_GREY}LOGIN                | SENHA   | PACOTE{C_RESET}")
    print(f"  {C_GREY}─────────────────────┼─────────┼──────────{C_RESET}")
    for i in lista: print(f"  {i} | {lbl}")

    # --- SALVAR EM ARQUIVO ---
    print(f"\n  {C_WHITE}DESEJA SALVAR EM ARQUIVO? (S/N){C_RESET}")
    save_op = input(f"  {C_RED}>>{C_RESET} ")
    if save_op.lower() == 's':
        try:
            filename = f"lote_{prefix}_{datetime.now().strftime('%d%m%H%M')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("===========================================\n")
                f.write(f" LOTE GERADO: {prefix.upper()} | DATA: {datetime.now().strftime('%d/%m/%Y')}\n")
                f.write(f" PACOTE: {lbl}\n")
                f.write("===========================================\n")
                f.write("LOGIN                | SENHA   | VALIDADE\n")
                f.write("---------------------+---------+-----------\n")
                for item in lista:
                    # Remove caracteres ANSI se houver (por segurança)
                    clean_item = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', item)
                    f.write(f"{clean_item} | {lbl}\n")
                f.write("===========================================\n")
            print(f"\n  {C_GREEN}✔ ARQUIVO SALVO: {filename}{C_RESET}")
        except Exception as e:
            print(f"\n  {C_RED}✖ ERRO AO SALVAR: {e}{C_RESET}")

    pause()

def criar_teste():
    draw_header()
    print(f"  {C_WHITE}>> CRIAR TESTE RÁPIDO{C_RESET}\n")
    u = f"teste{random.randint(100,999)}"
    p = "123456"
    print(f"  SUGESTÃO: {C_WHITE}{u}{C_RESET} / {C_WHITE}{p}{C_RESET}")
    custom = input(f"\n  {C_GREY}[ENTER] PARA ACEITAR OU DIGITE UM NOME:{C_RESET} ").strip()
    if custom: u = custom
    
    print(f"\n  {C_WHITE}[1]{C_RESET} 10 MIN  {C_WHITE}[2]{C_RESET} 30 MIN  {C_WHITE}[3]{C_RESET} 1 HORA  {C_WHITE}[4]{C_RESET} 24 HORAS")
    op = input(f"  {C_RED}>>{C_RESET} ")
    m = 30
    if op=='1': m=10
    elif op=='3': m=60
    elif op=='4': m=1440
    exp = datetime.now() + timedelta(minutes=m)
    
    try:
        with get_db() as conn:
            conn.cursor().execute("INSERT INTO users (username, password_hash, expiration_date) VALUES (?,?,?)", (u, generate_password_hash(p), exp))
            conn.commit()
        print(f"\n  {C_GREEN}✔ TESTE CRIADO! VÁLIDO ATÉ {exp.strftime('%H:%M')}{C_RESET}")
    except: print(f"\n  {C_RED}✖ ERRO AO CRIAR{C_RESET}")
    pause()

def listar_usuarios():
    draw_header()
    print(f"  {C_WHITE}>> DATABASE DE USUÁRIOS{C_RESET}\n")
    print(f"  {C_GREY}ID   LOGIN            STATUS       CONEXÃO      VENCIMENTO{C_RESET}")
    print(f"  {C_GREY}──── ──────────────── ──────────── ──────────── ────────────────{C_RESET}")
    
    with get_db() as conn:
        rows = conn.cursor().execute("SELECT id, username, expiration_date, session_token FROM users ORDER BY id DESC").fetchall()
        now = datetime.now()
        for r in rows:
            uid, nome, exp_raw, token = r
            if exp_raw is None:
                st = f"{C_YELLOW}PENDENTE{C_RESET}"
                venc = "1º Login"
                con = f"{C_GREY}---{C_RESET}"
            else:
                try: dt = datetime.strptime(exp_raw, '%Y-%m-%d %H:%M:%S.%f') if '.' in exp_raw else datetime.strptime(exp_raw, '%Y-%m-%d %H:%M:%S')
                except: dt = now
                if now < dt:
                    st = f"{C_GREEN}ATIVO   {C_RESET}"
                    con = f"{C_GREEN}● ONLINE{C_RESET}" if token else f"{C_GREY}○ OFF   {C_RESET}"
                else:
                    st = f"{C_RED}VENCIDO {C_RESET}"
                    con = f"{C_RED}EXPIRADO{C_RESET}"
                venc = dt.strftime("%d/%m %H:%M")
            print(f"  {pad_str(str(uid), 4)} {pad_str(nome[:15], 16)} {pad_str(st, 19)}  {pad_str(con, 19)} {venc}")
    print(f"\n  {C_GREY}Registros: {len(rows)}{C_RESET}")
    pause()

def gerenciar():
    draw_header()
    print(f"  {C_WHITE}>> GERENCIAMENTO INDIVIDUAL{C_RESET}\n")
    target = input(f"  {C_RED}DIGITE ID OU LOGIN:{C_RESET} ")
    with get_db() as conn:
        c = conn.cursor()
        if target.isdigit(): c.execute("SELECT id, username, expiration_date, duration_minutes FROM users WHERE id=?", (target,))
        else: c.execute("SELECT id, username, expiration_date, duration_minutes FROM users WHERE username=?", (target,))
        u = c.fetchone()
        if not u: 
            print(f"  {C_RED}✖ USUÁRIO NÃO ENCONTRADO{C_RESET}")
            pause(); return
        print(f"\n  {C_GREY}ALVO:{C_RESET} {C_WHITE}{u[1]}{C_RESET} [ID:{u[0]}]")
        print(f"\n  {C_WHITE}[1]{C_RESET} ADICIONAR TEMPO  {C_WHITE}[2]{C_RESET} MUDAR SENHA  {C_WHITE}[3]{C_RESET} KICK  {C_WHITE}[4]{C_RESET} DELETAR")
        op = input(f"\n  {C_RED}>>{C_RESET} ")
        if op == '1':
            h = int(input("  QUANTAS HORAS?: "))
            if u[2] is None:
                new_dur = (u[3] if u[3] else 0) + (h * 60)
                c.execute("UPDATE users SET duration_minutes=? WHERE id=?", (new_dur, u[0]))
                print(f"  {C_GREEN}✔ TEMPO ADICIONADO AO PACOTE PENDENTE{C_RESET}")
            else:
                try: base = datetime.strptime(u[2], '%Y-%m-%d %H:%M:%S.%f') if '.' in u[2] else datetime.strptime(u[2], '%Y-%m-%d %H:%M:%S')
                except: base = datetime.now()
                if base < datetime.now(): base = datetime.now()
                nova = base + timedelta(hours=h)
                c.execute("UPDATE users SET expiration_date=? WHERE id=?", (nova, u[0]))
                print(f"  {C_GREEN}✔ RENOVADO ATÉ {nova.strftime('%d/%m %H:%M')}{C_RESET}")
        elif op == '2':
            s = input("  NOVA SENHA: ")
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(s), u[0]))
            print(f"  {C_GREEN}✔ SENHA ATUALIZADA{C_RESET}")
        elif op == '3':
            c.execute("UPDATE users SET session_token=NULL WHERE id=?", (u[0],))
            print(f"  {C_YELLOW}✔ USUÁRIO DESCONECTADO{C_RESET}")
        elif op == '4':
            if input(f"  {C_RED}CONFIRMA (S/N)? {C_RESET}").lower()=='s':
                c.execute("DELETE FROM users WHERE id=?", (u[0],))
                print(f"  {C_RED}✔ REGISTRO DELETADO{C_RESET}")
        conn.commit()
    time.sleep(1)

def sistema():
    draw_header()
    print(f"  {C_WHITE}>> FERRAMENTAS AVANÇADAS{C_RESET}\n")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='maintenance'")
        is_man = cursor.fetchone()[0] == 'true'
    st = f"{C_GREEN}ATIVADO{C_RESET}" if is_man else f"{C_GREY}DESATIVADO{C_RESET}"
    print(f"  {C_WHITE}[1]{C_RESET} MODO MANUTENÇÃO [{st}]")
    print(f"  {C_WHITE}[2]{C_RESET} COMPENSAÇÃO GLOBAL (+TEMPO P/ TODOS)")
    print(f"  {C_WHITE}[3]{C_RESET} LIMPEZA AUTOMÁTICA (VENCIDOS)")
    print(f"  {C_WHITE}[4]{C_RESET} KICK ALL (RESETAR CONEXÕES)")
    op = input(f"\n  {C_RED}>>{C_RESET} ")
    if op == '1':
        with get_db() as conn: conn.cursor().execute("UPDATE settings SET value=? WHERE key='maintenance'", ('false' if is_man else 'true',)); conn.commit()
        print(f"  {C_GREEN}✔ STATUS ATUALIZADO{C_RESET}")
    elif op == '2':
        h = int(input("  ADICIONAR HORAS A TODOS: "))
        loading("APLICANDO BÔNUS")
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT id, expiration_date FROM users WHERE expiration_date IS NOT NULL")
            for r in c.fetchall():
                try: dt = datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S.%f') if '.' in r[1] else datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S')
                except: continue
                c.execute("UPDATE users SET expiration_date=? WHERE id=?", (dt + timedelta(hours=h), r[0]))
            c.execute("UPDATE users SET duration_minutes = duration_minutes + ? WHERE expiration_date IS NULL", (h*60,))
            conn.commit()
        print(f"  {C_GREEN}✔ EXECUTADO{C_RESET}")
    elif op == '3':
        with get_db() as conn: conn.cursor().execute("DELETE FROM users WHERE expiration_date < ? AND expiration_date IS NOT NULL", (datetime.now(),)); conn.commit()
        print(f"  {C_GREEN}✔ DATABASE LIMPA{C_RESET}")
    elif op == '4':
        with get_db() as conn: conn.cursor().execute("UPDATE users SET session_token=NULL"); conn.commit()
        print(f"  {C_GREEN}✔ CONEXÕES RESETADAS{C_RESET}")
    time.sleep(1)

def main():
    init_db()
    while True:
        draw_header()
        dashboard()
        print(f"  {C_WHITE}MENU DE COMANDO:{C_RESET}")
        print(f"  {C_GREY}──────────────────────────────────────────────────────────────────{C_RESET}")
        print(f"  {C_RED}[1]{C_RESET} CRIAR ACESSO        {C_RED}[4]{C_RESET} GERAR LOTE (REVENDA)")
        print(f"  {C_RED}[2]{C_RESET} DATABASE (LISTAR)   {C_RED}[5]{C_RESET} TESTE RÁPIDO")
        print(f"  {C_RED}[3]{C_RESET} GERENCIAR / EDITAR  {C_RED}[6]{C_RESET} SISTEMA & MANUTENÇÃO")
        print(f"  {C_GREY}──────────────────────────────────────────────────────────────────{C_RESET}")
        print(f"  {C_RED}[0]{C_RESET} SAIR DA AREA 51")
        op = input(f"\n  {C_RED}>>{C_RESET} ")
        if op == '1': criar_manual()
        elif op == '2': listar_usuarios()
        elif op == '3': gerenciar()
        elif op == '4': gerar_lote()
        elif op == '5': criar_teste()
        elif op == '6': sistema()
        elif op == '0': clear(); sys.exit()

if __name__ == "__main__":
    main()
