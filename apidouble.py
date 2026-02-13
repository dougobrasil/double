import sys
import asyncio
import aiohttp
import uvicorn
from datetime import datetime
from threading import Thread
from fastapi import FastAPI
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QPushButton, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor

# --- CONFIGURAÇÃO DA API WEB ---
api_app = FastAPI()
latest_data_store = {"status": "offline", "items": [], "updated_at": ""}

@api_app.get("/api")
async def get_api_data():
    return latest_data_store

# --- ENGINE DE CAPTURA ---
class BackendWorker(QThread):
    data_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        # Inicia o servidor apenas uma vez
        self.server_thread = Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.fetch_loop())

    def run_server(self):
        uvicorn.run(api_app, host="127.0.0.1", port=8000, log_level="error")

    async def fetch_loop(self):
        global latest_data_store
        url_recent = "https://blaze.bet.br/api/singleplayer-originals/originals/roulette_games/recent/1"
        url_current = "https://blaze.bet.br/api/singleplayer-originals/originals/roulette_games/current/1"
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            while True:
                if self.running:
                    try:
                        async with session.get(url_recent, timeout=5) as r_rec, \
                                   session.get(url_current, timeout=5) as r_curr:
                            if r_rec.status == 200:
                                payload = {
                                    "status": (await r_curr.json()).get("status", "unknown"),
                                    "items": await r_rec.json(),
                                    "updated_at": datetime.now().strftime("%H:%M:%S")
                                }
                                latest_data_store = payload
                                self.data_signal.emit(payload)
                    except:
                        self.error_signal.emit("Erro de conexão...")
                await asyncio.sleep(2)

    def stop(self):
        self.running = False
        global latest_data_store
        latest_data_store = {"status": "offline", "items": [], "updated_at": ""}

# --- INTERFACE ---
class BlazeTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blaze Control Panel")
        self.setFixedSize(850, 420)
        self.setStyleSheet("QMainWindow { background-color: #0b0e11; }")
        
        self.worker = BackendWorker()
        self.worker.data_signal.connect(self.update_ui)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)

        # Header
        header = QHBoxLayout()
        v_title = QVBoxLayout()
        self.main_title = QLabel("BLAZE MONITOR PRO")
        self.main_title.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        self.status_lbl = QLabel("SISTEMA DESLIGADO")
        self.status_lbl.setStyleSheet("color: #474d57; font-size: 12px; font-weight: bold;")
        v_title.addWidget(self.main_title)
        v_title.addWidget(self.status_lbl)
        header.addLayout(v_title)
        header.addStretch()
        
        self.time_lbl = QLabel("--:--:--")
        self.time_lbl.setStyleSheet("font-size: 22px; color: #f12c4c; font-family: 'Consolas';")
        header.addWidget(self.time_lbl)
        layout.addLayout(header)

        # Board
        self.res_frame = QFrame()
        self.res_frame.setStyleSheet("background-color: #161a1e; border-radius: 15px; border: 1px solid #2b2f36;")
        self.res_layout = QHBoxLayout(self.res_frame)
        self.res_layout.setContentsMargins(20, 40, 20, 40)
        layout.addWidget(self.res_frame)

        # Botões de Controle
        btn_layout = QHBoxLayout()
        
        self.btn_on = QPushButton("LIGAR CAPTURA")
        self.btn_on.setCursor(Qt.PointingHandCursor)
        self.btn_on.setStyleSheet("""
            QPushButton { background-color: #00c853; color: white; font-weight: bold; border-radius: 8px; padding: 15px; }
            QPushButton:hover { background-color: #00e676; }
        """)
        self.btn_on.clicked.connect(self.start_system)

        self.btn_off = QPushButton("DESLIGAR")
        self.btn_off.setCursor(Qt.PointingHandCursor)
        self.btn_off.setStyleSheet("""
            QPushButton { background-color: #ff1744; color: white; font-weight: bold; border-radius: 8px; padding: 15px; }
            QPushButton:hover { background-color: #ff5252; }
        """)
        self.btn_off.clicked.connect(self.stop_system)

        btn_layout.addWidget(self.btn_on)
        btn_layout.addWidget(self.btn_off)
        layout.addLayout(btn_layout)

    def start_system(self):
        if not self.worker.isRunning():
            self.worker.start()
        self.worker.running = True
        self.status_lbl.setText("API ONLINE: http://localhost:8000/api")
        self.status_lbl.setStyleSheet("color: #00ff7f; font-size: 12px; font-weight: bold;")

    def stop_system(self):
        self.worker.stop()
        self.status_lbl.setText("SISTEMA DESLIGADO")
        self.status_lbl.setStyleSheet("color: #474d57; font-size: 12px; font-weight: bold;")
        self.time_lbl.setText("--:--:--")
        while self.res_layout.count():
            item = self.res_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def update_ui(self, data):
        if not self.worker.running: return
        self.time_lbl.setText(data['updated_at'])
        while self.res_layout.count():
            item = self.res_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for item in data['items'][:12]:
            bg = "#f12c4c" if item['color'] == 1 else "#262f3c" if item['color'] == 2 else "#ffffff"
            tx = "white" if item['color'] != 0 else "#0b0e11"
            card = QLabel(str(item['roll']))
            card.setFixedSize(50, 50)
            card.setAlignment(Qt.AlignCenter)
            card.setStyleSheet(f"background-color: {bg}; color: {tx}; border-radius: 10px; font-size: 18px; font-weight: bold;")
            self.res_layout.addWidget(card)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BlazeTerminal()
    window.show()
    sys.exit(app.exec_())
