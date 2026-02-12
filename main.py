import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQ_UPDATE = "last_update.txt"

# ==================== TELEGRAM ====================
def enviar_telegram(mensagem, chat_id=CHAT_ID):
    if not mensagem: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def ler_ultima_mensagem():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=15).json()
        if not res.get("result"): return None

        ultima = res["result"][-1]
        texto = ultima.get("message", {}).get("text", "").lower()
        cid = ultima.get("message", {}).get("chat", {}).get("id")
        update_id = ultima.get("update_id")

        if os.path.exists(ARQ_UPDATE):
            with open(ARQ_UPDATE, "r") as f:
                if str(update_id) == f.read().strip(): return None

        with open(ARQ_UPDATE, "w") as f:
            f.write(str(update_id))

        return texto, cid
    except:
        return None

# ==================== CLIMA (LÓGICA REFEITA) ====================
def verificar_clima(nome, lat, lon):
    # Adicionado weather_code para detectar trovoadas
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover,weather_code"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=15).json()
        dados = res["current"]
        chuva = dados["precipitation"]
        is_day = dados["is_day"]
        nuvens = dados["cloud_cover"]
        code = dados["weather_code"]

        # LÓGICA DE EMOJIS
        if code in [95, 96, 99]: # Códigos da API para Trovoadas
            emoji = "⛈️"
        elif chuva > 0:
            emoji = "🌧️" # Nuvem com gotinhas
        else:
            if is_day:
                emoji = "☀️" if nuvens < 25 else "⛅"
            else:
                # Noite: se tiver muita nuvem (nublado), só a nuvem. Se não, a Lua.
                emoji = "🌙" if nuvens < 25 else "☁️"

        status_texto = f"{chuva} mm agora" if chuva > 0 else "Sem chuva agora"
        return f"{emoji} *{nome}:* {status_texto}"
    except:
        return f"❌ *{nome}:* Erro na consulta"

# ==================== PROCESSAMENTO ====================
def executar():
    fuso_br = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_br)
    
    # 1. Verifica se houve comando manual
    msg_info = ler_ultima_mensagem()
    if msg_info:
        texto, chat_id_remetente = msg_info
        if any(k in texto for k in ["agora", "status", "chuva"]):
            df = pd.read_csv(ARQUIVO)
            respostas = ["📍 *RELATÓRIO DE BARRAGENS*\n"]
            for _, row in df.iterrows():
                respostas.append(verificar_clima(row['nome'], row['lat'], row['long']))
            enviar_telegram("\n".join(respostas), chat_id_remetente)
            return

    # 2. Relatório Automático (Job 1h)
    df = pd.read_csv(ARQUIVO)
    relatorio = [
        f"🛰 *RELATÓRIO BARRAGENS*",
        f"⏰ {agora.strftime('%d/%m %H:%M')}\n"
    ]
    for _, row in df.iterrows():
        relatorio.append(verificar_clima(row['nome'], row['lat'], row['long']))

    enviar_telegram("\n".join(relatorio))

if __name__ == "__main__":
    executar()
