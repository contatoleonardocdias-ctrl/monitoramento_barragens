import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# No GitHub, configure o segredo TOMORROW_TOKEN com a sua chave
TOMORROW_API_KEY = os.getenv("TOMORROW_TOKEN") 
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    fuso_sp = timezone(timedelta(hours=-3))
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            with pd.ExcelFile(ARQUIVO_EXCEL, engine='openpyxl') as xls:
                df_bruta = pd.read_excel(xls, "Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], format='%d/%m/%Y')
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')
    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    aba_resumo.columns = ['Barragem', 'Mês', 'Total Acumulado (mm)']
    aba_resumo['Última Atualização'] = datetime.now(fuso_sp).strftime('%d/%m %H:%M')

    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.drop(columns=['Data_dt', 'Mês']).to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    requests.post(url, data=payload, timeout=25)

def verificar_clima(nome, lat, lon):
    # Usando o endpoint de Realtime para precisão imediata
    url = f"https://api.tomorrow.io/v4/weather/realtime?location={lat},{lon}&apikey={TOMORROW_API_KEY}"
    
    try:
        res = requests.get(url, timeout=25).json()
        # A estrutura da Tomorrow.io é data -> values
        valores = res.get("data", {}).get("values", {})
        
        chuva = valores.get("precipitationIntensity", 0.0)
        probabilidade = valores.get("precipitationProbability", 0)
        temp = valores.get("temperature", 0.0)
        nuvens = valores.get("cloudCover", 0)
        
        agora = datetime.now(timezone(timedelta(hours=-3)))

        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'),
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(),
            "Precipitacao (mm)": chuva,
            "Temp (C)": temp
        }

        if chuva > 0 or probabilidade > 30:
            status = (f"⚠️ **ALERTA: {chuva:.2f}mm/h**\n"
                      f"🌡️ Temp: {temp:.1f}°C\n"
                      f"🎲 Probabilidade: {probabilidade}%")
        else:
            status = f"🌡️ {temp:.1f}°C\n☀️ Sem chuva (Nuvens: {nuvens}%)"

        return f"📍 *{nome.upper()}*\n{status}\n", dados_planilha
    except Exception as e:
        return f"📍 *{nome.upper()}*\n❌ Erro na API\n", None

def executar():
    if not os.path.exists(ARQUIVO): return
    df = pd.read_csv(ARQUIVO)
    corpo = ["🛰️ **MONITORAMENTO PRECISÃO**\n---"]
    dados_excel = []

    for _, row in df.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo.append(msg)
        if dados: dados_excel.append(dados)

    if dados_excel: atualizar_planilha_excel(dados_excel)
    enviar_telegram("\n".join(corpo))

if __name__ == "__main__":
    executar()
