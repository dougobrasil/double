import asyncio
import aiohttp
import uvicorn
from datetime import datetime
from threading import Thread
from fastapi import FastAPI

# --- CONFIGURAÇÃO DA API WEB ---
api_app = FastAPI()
# Armazena os dados globais para que a rota /api possa acessá-los
latest_data_store = {"status": "offline", "items": [], "updated_at": ""}

@api_app.get("/api")
async def get_api_data():
    return latest_data_store

# --- ENGINE DE CAPTURA (CMD VERSION) ---
class BlazeEngine:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True
        print(f"[*] Engine iniciada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Inicia o servidor FastAPI em uma thread separada
        server_thread = Thread(target=self.run_server, daemon=True)
        server_thread.start()
        
        # Inicia o loop de captura de dados
        asyncio.run(self.fetch_loop())

    def run_server(self):
        # Roda o servidor na porta 8000
        uvicorn.run(api_app, host="127.0.0.1", port=8000, log_level="error")

    async def fetch_loop(self):
        global latest_data_store
        url_recent = "https://blaze.bet.br/api/singleplayer-originals/originals/roulette_games/recent/1"
        url_current = "https://blaze.bet.br/api/singleplayer-originals/originals/roulette_games/current/1"
        
        print("[+] Monitorando API da Blaze...")
        print("[!] API Online em: http://127.0.0.1:8000/api")
        print("[-] Pressione Ctrl+C para encerrar.\n")

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            while self.running:
                try:
                    async with session.get(url_recent, timeout=5) as r_rec, \
                               session.get(url_current, timeout=5) as r_curr:
                        
                        if r_rec.status == 200 and r_curr.status == 200:
                            data_recent = await r_rec.json()
                            data_current = await r_curr.json()
                            
                            payload = {
                                "status": data_current.get("status", "unknown"),
                                "items": data_recent,
                                "updated_at": datetime.now().strftime("%H:%M:%S")
                            }
                            
                            latest_data_store = payload
                            
                            # Log visual simplificado no CMD
                            last_roll = data_recent[0]['roll']
                            color_str = "VERMELHO" if data_recent[0]['color'] == 1 else "PRETO" if data_recent[0]['color'] == 2 else "BRANCO"
                            print(f"[{payload['updated_at']}] Último: {last_roll} ({color_str}) | Status: {payload['status']}")
                            
                except Exception as e:
                    print(f"[!] Erro de conexão: {e}")
                
                await asyncio.sleep(2)

if __name__ == "__main__":
    engine = BlazeEngine()
    try:
        engine.start()
    except KeyboardInterrupt:
        print("\n[!] Sistema encerrado pelo usuário.")
