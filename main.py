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
    if not mensagem or not TOKEN: 
        print("⚠️ Erro: Mensagem vazia ou Token não configurado.")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": mensagem, 
        "parse_mode": "Markdown"
    }
    
    try:
        # Usando data= para evitar problemas de parse no Telegram
        res = requests.post(url, data=payload, timeout=20)
        if res.status_code == 200:
            print(f"✅ Mensagem enviada!")
        else:
            print(f"❌ Erro Telegram: {res.text}")
    except Exception as e:
        print(f"⚠️ Falha de rede no Telegram: {e}")

def ler_ultima_mensagem():
    if not TOKEN: return None
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

# ==================== CLIMA ====================
def verificar_clima(nome, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,is_day,cloud_cover"
        f"&hourly=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=20).json()
        chuva_agora = res["current"]["precipitation"]
        chuva_prev = res["hourly"]["precipitation"][1]
        is_day = res["current"]["is_day"]
        nuvens = res["current"]["cloud_cover"]

        # Define se deve disparar alerta
        tem_chuva = (chuva_agora > 0 or chuva_prev > 0)
        
        # Monta a parte do texto (emoji e status)
        if tem_chuva:
            emoji = "⚠️🌧️"
            status = f"{chuva_agora:.1f}mm agora (Previsto {chuva_prev:.1f}mm próxima hora)"
        else:
            emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status = "SEM CHUVA"

        return emoji, status, tem_chuva
    except Exception as e:
        print(f"Erro clima {nome}: {e}")
        return "❌", "Erro na consulta", False

# ==================== EXECUÇÃO PRINCIPAL ====================
def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_str = agora.strftime('%d/%m/%Y %H:%M')
    
    print(f"--- Iniciando Verificação: {data_str} ---")
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    
    # 1. COMANDO MANUAL (STATUS)
    msg_info = ler_ultima_mensagem()
    if msg_info:
        texto, cid = msg_info
        if any(k in texto for k in ["status", "chuva", "agora", "barragem"]):
            relatorio = ["🛰️ *STATUS DAS BARRAGENS*", f"⏰ {data_str}\n"]
            for _, row in df.iterrows():
                emoji, status, _ = verificar_clima(row['nome'], row['lat'], row['long'])
                relatorio.append(f"{emoji} - *{row['nome'].upper()}:* {status}")
            enviar_telegram("\n".join(relatorio), cid)
            return

    # 2. MONITORAMENTO AUTOMÁTICO (ALERTAS)
    for _, row in df.iterrows():
        emoji, status, tem_chuva = verificar_clima(row['nome'], row['lat'], row['long'])
        
        if tem_chuva:
            # Formatação idêntica ao seu print original
            alerta = (
                f"⚠️ **ALERTA DE CHUVA - {row['nome'].upper()}**\n\n"
                f"🌧️ **Tempo Real:** Está chovendo {status.split(' (')[0]}!\n\n"
                f"⏰ Atualizado em: {data_str}"
            )
            enviar_telegram(alerta)
        else:
            print(f"OK: {row['nome']} sem chuva.")

if __name__ == "__main__":
    executar()
