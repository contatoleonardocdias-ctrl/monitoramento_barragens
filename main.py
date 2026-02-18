import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# CONFIGURAÇÕES
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO_BARRAGENS = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    fuso_sp = timezone(timedelta(hours=-3))
    hoje_str = datetime.now(fuso_sp).strftime('%d/%m/%Y')

    if os.path.exists(ARQUIVO_EXCEL):
        try:
            with pd.ExcelFile(ARQUIVO_EXCEL, engine='openpyxl') as xls:
                df_bruta = pd.read_excel(xls, "Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    df_bruta['Data'] = df_bruta['Data'].astype(str)
    df_hoje = df_bruta[df_bruta['Data'] == hoje_str]
    
    aba_acumulado = df_hoje.groupby('Barragem')['Precipitacao (mm)'].sum().reset_index()
    aba_acumulado.columns = ['Barragem', 'Total Acumulado Hoje (mm)']
    aba_acumulado['Ultima Leitura'] = datetime.now(fuso_sp).strftime('%H:%M')

    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_acumulado.to_excel(writer, sheet_name="Total Dia", index=False)

def enviar_mensagem_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"})

def verificar_clima(nome, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,temperature_2m&timezone=America%2FSao_Paulo"
    try:
        res = requests.get(url, timeout=25).json()
        curr = res.get("current", {})
        chuva = curr.get("precipitation") if curr.get("precipitation") is not None else 0.0
        temp = curr.get("temperature_2m") if curr.get("temperature_2m") is not None else 0.0
        agora = datetime.now(timezone(timedelta(hours=-3)))
        return {"Data": agora.strftime('%d/%m/%Y'), "Hora": agora.strftime('%H:%M'), "Barragem": nome.upper(), "Precipitacao (mm)": chuva, "Temp (C)": temp}
    except: return None

def executar():
    if not os.path.exists(ARQUIVO_BARRAGENS): return
    df_lista = pd.read_csv(ARQUIVO_BARRAGENS)
    lista_dados = []
    
    for _, row in df_lista.iterrows():
        dados = verificar_clima(row['nome'], row['lat'], row['long'])
        if dados: lista_dados.append(dados)

    if lista_dados:
        atualizar_planilha_excel(lista_dados)
        # Avisa apenas que os dados foram salvos na nuvem
        agora_str = datetime.now(timezone(timedelta(hours=-3))).strftime('%H:%M')
        enviar_mensagem_telegram(f"✅ **Dados Coletados ({agora_str})**\nAs informações foram salvas na planilha do GitHub.")

if __name__ == "__main__":
    executar()
