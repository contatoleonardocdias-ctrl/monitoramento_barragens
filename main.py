import requests
import os
import pandas as pd
from datetime import datetime

# ==================== CONFIGURAÇÕES ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO_BARRAGENS = "barragens.csv"

def enviar_telegram(mensagem):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Erro Telegram: {e}")

def verificar_clima(nome, lat, lon):
    # API Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=1"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        chuva_agora = data['current']['precipitation']
        
        # Lógica de previsão próxima hora
        hora_iso = datetime.now().strftime('%Y-%m-%dT%H:00')
        indices = data['hourly']['time']
        try:
            idx = indices.index(hora_iso)
            chuva_prevista = data['hourly']['precipitation'][idx + 1] if idx + 1 < len(indices) else 0
        except:
            chuva_prevista = 0

        # Dispara alerta se houver qualquer chuva
        if chuva_agora > 0 or chuva_prevista > 0:
            msg = (
                f"⚠️ *ALERTA: {nome.upper()}*\n\n"
                f"🌧 *Chovendo agora:* {chuva_agora}mm\n"
                f"📅 *Próxima hora:* {chuva_prevista}mm\n"
                f"⏰ _Sincronizado: {datetime.now().strftime('%H:%M')}_"
            )
            enviar_telegram(msg)
            return f"Alerta enviado: {nome}"
        
        return f"{nome}: Sem chuva."
    except Exception as e:
        return f"Erro em {nome}: {e}"

def executar():
    if not os.path.exists(ARQUIVO_BARRAGENS):
        print("Erro: Arquivo barragens.csv não encontrado!")
        return

    # Lendo o CSV (ajustado para suas colunas: nome, lat, long)
    df = pd.read_csv(ARQUIVO_BARRAGENS)
    
    for _, row in df.iterrows():
        # ATENÇÃO: Os nomes abaixo devem ser iguais aos da sua planilha
        res = verificar_clima(row['nome'], row['lat'], row['long'])
        print(res)

if __name__ == "__main__":
    executar()
