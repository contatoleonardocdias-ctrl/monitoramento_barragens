import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID:
        print("❌ ERRO: CHAT_ID ou TOKEN não configurados.")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": str(CHAT_ID).strip(), 
        "text": mensagem, 
        "parse_mode": "Markdown"
    }
    
    try:
        res = requests.post(url, data=payload, timeout=25)
        if res.status_code != 200:
            print(f"❌ Erro Telegram: {res.text}")
    except Exception as e:
        print(f"⚠️ Falha de rede: {e}")

def verificar_clima(nome, lat, lon):
    # Mudamos para buscar precipitação e chuva (rain) das últimas horas também
    # Isso evita perder chuvas rápidas que a API 'esquece' no tempo real
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,rain,showers,cloud_cover,is_day"
        f"&hourly=precipitation"
        f"&past_hours=3"  # Busca as últimas 3 horas para conferir se REALMENTE choveu
        f"&timezone=America%2FSao_Paulo"
    )
    
    try:
        res = requests.get(url, timeout=25).json()
        
        # Dados atuais (Soma de chuva contínua + pancadas)
        chuva_agora = res["current"]["precipitation"]
        
        # Histórico recente (últimas 2 horas) - Se choveu e a API já limpou o 'current', pegamos aqui
        chuva_recente = sum(res["hourly"]["precipitation"][-3:-1]) 
        
        # Previsão próxima hora
        # O índice [-1] após as past_hours costuma ser a próxima hora cheia
        chuva_prevista = res["hourly"]["precipitation"][-1]
        
        is_day = res["current"]["is_day"]
        nuvens = res["current"]["cloud_cover"]

        # Se choveu agora, recentemente ou vai chover logo
        if chuva_agora > 0 or chuva_recente > 0 or chuva_prevista > 0:
            intensidade = "Fraca" if (chuva_agora + chuva_recente) < 5 else "Moderada" if (chuva_agora + chuva_recente) < 15 else "FORTE"
            
            status_formatado = (
                f"⚠️ **ALERTA DE CHUVA ({intensidade})**\n"
                f"🌧️ **Agora:** {chuva_agora:.1f}mm\n"
                f"🕒 **Acumulado recente:** {chuva_recente:.1f}mm\n"
                f"🔮 **Próxima hora:** {chuva_prevista:.1f}mm"
            )
        else:
            emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status_formatado = f"{emoji} Sem chuva registrada"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n"
    
    except Exception as e:
        return f"📍 *{nome.upper()}*\n❌ Erro: {str(e)[:50]}\n"

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_str = agora.strftime('%d/%m/%Y %H:%M')
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    df = pd.read_csv(ARQUIVO)
    corpo_mensagem = [
        "🛰️ **MONITORAMENTO HÍDRICO**",
        f"⏰ {data_str}\n",
        "---"
    ]
    
    for _, row in df.iterrows():
        info_barragem = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(info_barragem)

    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
