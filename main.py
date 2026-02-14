import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
# Certifique-se de que essas variáveis existam no seu ambiente
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQ_UPDATE = "last_update.txt"

# ==================== TELEGRAM ====================
def enviar_telegram(mensagem, chat_id=CHAT_ID):
    if not mensagem: 
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": mensagem, 
        "parse_mode": "Markdown"
    }
    
    try:
        # Usamos data= em vez de json= para maior compatibilidade com a API
        res = requests.post(url, data=payload, timeout=15)
        if res.status_code == 200:
            print(f"✅ Mensagem enviada com sucesso!")
        else:
            print(f"❌ Erro API Telegram ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"⚠️ Falha na conexão com Telegram: {e}")

def ler_ultima_mensagem():
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=15).json()
        if not res.get("result"): 
            return None
        
        ultima = res["result"][-1]
        texto = ultima.get("message", {}).get("text", "").lower()
        cid = ultima.get("message", {}).get("chat", {}).get("id")
        update_id = ultima.get("update_id")
        
        # Evita processar a mesma mensagem repetidamente
        if os.path.exists(ARQ_UPDATE):
            with open(ARQ_UPDATE, "r") as f:
                if str(update_id) == f.read().strip(): 
                    return None
        
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
        res = requests.get(url, timeout=15).json()
        atual = res["current"]
        chuva_agora = atual["precipitation"]
        chuva_prev = res["hourly"]["precipitation"][1] 
        
        is_day = atual["is_day"]
        nuvens = atual["cloud_cover"]

        # Determina se há alerta de chuva
        esta_chovendo = chuva_agora > 0 or chuva_prev > 0

        if esta_chovendo:
            emoji = "⚠️🌧️"
            status_texto = f"Está chovendo {chuva_agora:.1f}mm agora! (Previsto {chuva_prev:.1f}mm próxima hora)"
        else:
            if is_day:
                emoji = "☀️" if nuvens < 25 else "⛅"
            else:
                emoji = "🌙" if nuvens < 25 else "☁️"
            status_texto = "SEM CHUVA"

        msg = f"{emoji} - *{nome.upper()}:* {status_texto}"
        return msg, esta_chovendo

    except Exception as e:
        return f"❌ - *{nome.upper()}:* Erro na consulta", False

# ==================== PROCESSAMENTO ====================
def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_formatada = agora.strftime('%d/%m/%Y %H:%M')
    
    print(f"--- Iniciando Verificação: {data_formatada} ---")
    
    if not os.path.exists(ARQUIVO):
        print(f"Erro: Arquivo {ARQUIVO} não encontrado.")
        return

    df = pd.read_csv(ARQUIVO)
    
    # 1. VERIFICA COMANDO MANUAL
    msg_info = ler_ultima_mensagem()
    if msg_info:
        texto, cid = msg_info
        if any(k in texto for k in ["agora", "status", "chuva", "barragem"]):
            print(f"Comando manual recebido: {texto}")
            respostas = ["🛰️ *RELATÓRIO DE STATUS*", f"⏰ {data_formatada}\n"]
            for _, row in df.iterrows():
                msg_clima, _ = verificar_clima(row['nome'], row['lat'], row['long'])
                respostas.append(msg_clima)
            
            enviar_telegram("\n".join(respostas), cid)
            return # Interrompe aqui para não duplicar o envio automático

    # 2. VERIFICAÇÃO AUTOMÁTICA (ALERTAS)
    print("Verificando sensores de chuva...")
    for _, row in df.iterrows():
        msg_clima, tem_chuva = verificar_clima(row['nome'], row['lat'], row['long'])
        
        if tem_chuva:
            # Monta o alerta igual ao do seu print
            alerta = (
                f"⚠️ **ALERTA DE CHUVA - {row['nome'].upper()}**\n\n"
                f"🌧️ **Tempo Real:** {msg_clima.split(': ')[1]}\n\n"
                f"⏰ Atualizado em: {data_formatada}"
            )
            enviar_telegram(alerta)
        else:
            print(f"ℹ️ {row['nome']}: Céu limpo/nublado.")

if __name__ == "__main__":
    executar()
