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
        if res.status_code == 200:
            print("✅ Relatório enviado com sucesso!")
        else:
            print(f"❌ Erro Telegram: {res.text}")
    except Exception as e:
        print(f"⚠️ Falha de rede: {e}")

def verificar_clima(nome, lat, lon):
    # Adicionado 'temperature_2m' para pegar a temperatura atual
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,temperature_2m,cloud_cover,is_day"
        f"&hourly=precipitation"
        f"&past_hours=3"
        f"&timezone=America%2FSao_Paulo"
    )
    
    try:
        res = requests.get(url, timeout=25).json()
        
        # --- TRATAMENTO SEGURO DE DADOS ---
        current_data = res.get("current", {})
        temp_atual = current_data.get("temperature_2m") # Temperatura em Celsius
        chuva_agora = current_data.get("precipitation") or 0.0
        is_day = current_data.get("is_day", 1)
        nuvens = current_data.get("cloud_cover", 0)
        
        # Tratamento da lista horária
        lista_hourly = res.get("hourly", {}).get("precipitation", [])
        lista_limpa = [n if n is not None else 0.0 for n in lista_hourly]
        
        if len(lista_limpa) >= 4:
            chuva_recente = sum(lista_limpa[-4:-1])
            chuva_prevista = lista_limpa[-1]
        else:
            chuva_recente = 0.0
            chuva_prevista = 0.0

        # Formatação da temperatura
        txt_temp = f"🌡️ **Temp:** {temp_atual}°C" if temp_atual is not None else "🌡️ Temp: --"

        # --- LÓGICA DE STATUS ---
        if chuva_agora > 0 or chuva_recente > 0 or chuva_prevista > 0:
            total_visto = chuva_agora + chuva_recente
            if total_visto < 2: intensidade = "Garoa"
            elif total_visto < 10: intensidade = "Moderada"
            else: intensidade = "FORTE"
            
            status_formatado = (
                f"{txt_temp}\n"
                f"⚠️ **ALERTA DE CHUVA ({intensidade})**\n"
                f"🌧️ **Agora:** {chuva_agora:.1f}mm\n"
                f"🕒 **Acumulado (3h):** {chuva_recente:.1f}mm\n"
                f"🔮 **Previsão (1h):** {chuva_prevista:.1f}mm"
            )
        else:
            emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            status_formatado = f"{txt_temp}\n{emoji} Sem chuva registrada"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n"
    
    except Exception as e:
        return f"📍 *{nome.upper()}*\n❌ Erro nos dados: {str(e)[:40]}\n"

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    data_str = agora.strftime('%d/%m/%Y %H:%M')
    
    if not os.path.exists(ARQUIVO):
        print(f"❌ Arquivo {ARQUIVO} não encontrado!")
        return

    try:
        df = pd.read_csv(ARQUIVO)
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return
    
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
