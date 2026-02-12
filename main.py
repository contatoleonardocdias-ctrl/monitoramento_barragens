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
        print("❌ ERRO: Chaves não encontradas!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=15)
        print("✅ Relatório enviado ao Telegram!" if res.status_code == 200 else f"❌ Erro API: {res.text}")
    except Exception as e:
        print(f"❌ Erro conexão: {e}")

def verificar_clima(nome, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=1"
    try:
        res = requests.get(url, timeout=15).json()
        chuva_agora = res['current']['precipitation']
        
        # Ajuste de hora para busca na previsão (UTC-3)
        fuso_br = timezone(timedelta(hours=-3))
        hora_iso = datetime.now(fuso_br).strftime('%Y-%m-%dT%H:00')
        
        indices = res['hourly']['time']
        try:
            idx = indices.index(hora_iso)
            chuva_prev = res['hourly']['precipitation'][idx + 1]
        except:
            chuva_prev = 0

        if chuva_agora > 0 or chuva_prev > 0:
            return f"⚠️ *{nome}:* {chuva_agora}mm agora / {chuva_prev}mm prev."
        return f"✅ *{nome}:* Sem chuva"
    except:
        return f"❌ *{nome}:* Erro na consulta"

def executar():
    if not os.path.exists(ARQUIVO):
        print("Arquivo CSV não encontrado!")
        return

    # Definindo horário de Brasília para o cabeçalho
    fuso_br = timezone(timedelta(hours=-3))
    agora_br = datetime.now(fuso_br)
    
    df = pd.read_csv(ARQUIVO)
    relatorio = [f"🛰 *RELATÓRIO BARRAGENS*\n⏰ {agora_br.strftime('%d/%m/%Y %H:%M')}\n"]
    
    for _, row in df.iterrows():
        status = verificar_clima(row['nome'], row['lat'], row['long'])
        relatorio.append(status)
        print(status)

    enviar_telegram("\n".join(relatorio))

if __name__ == "__main__":
    executar()
