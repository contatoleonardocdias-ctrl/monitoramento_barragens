import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO_BARRAGENS = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    fuso_sp = timezone(timedelta(hours=-3))
    hoje_str = datetime.now(fuso_sp).strftime('%d/%m/%Y')

    # Carrega ou cria a Base Bruta
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            with pd.ExcelFile(ARQUIVO_EXCEL) as xls:
                df_bruta = pd.read_excel(xls, "Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    # Gera Aba de Acumulado Diário
    df_bruta['Data'] = df_bruta['Data'].astype(str)
    df_hoje = df_bruta[df_bruta['Data'] == hoje_str]
    
    aba_acumulado = df_hoje.groupby('Barragem')['Precipitacao (mm)'].sum().reset_index()
    aba_acumulado.columns = ['Barragem', 'Total Acumulado Hoje (mm)']
    aba_acumulado['Ultima Leitura'] = datetime.now(fuso_sp).strftime('%H:%M')

    # Salva com openpyxl
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_acumulado.to_excel(writer, sheet_name="Total Dia", index=False)

def enviar_arquivo_telegram():
    """Envia a planilha atualizada para o seu Telegram"""
    if not TOKEN or not CHAT_ID or not os.path.exists(ARQUIVO_EXCEL): return
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    try:
        with open(ARQUIVO_EXCEL, 'rb') as f:
            requests.post(url, data={"chat_id": CHAT_ID}, files={"document": f}, timeout=30)
    except:
        pass

def enviar_mensagem_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    requests.post(url, data=payload, timeout=25)

def verificar_clima(nome, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,temperature_2m,is_day,cloud_cover&timezone=America%2FSao_Paulo"
    try:
        res = requests.get(url, timeout=25).json()
        curr = res.get("current", {})
        chuva = curr.get("precipitation") or 0.0
        temp = curr.get("temperature_2m")
        fuso_sp = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_sp)
        
        dados = {
            "Data": agora.strftime('%d/%m/%Y'),
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(),
            "Precipitacao (mm)": chuva,
            "Temp (C)": temp
        }
        status = f"🌡️ **{temp}°C** | 🌧️ **Agora:** {chuva}mm" if chuva > 0 else f"🌡️ **{temp}°C** | Sem chuva"
        return f"📍 *{nome.upper()}*\n{status}\n", dados
    except:
        return f"📍 *{nome.upper()}*\n❌ Erro\n", None

def executar():
    if not os.path.exists(ARQUIVO_BARRAGENS): return
    df_lista = pd.read_csv(ARQUIVO_BARRAGENS)
    fuso_sp = timezone(timedelta(hours=-3))
    corpo_msg = [f"🛰️ **RELATÓRIO HÍDRICO**\n⏰ {datetime.now(fuso_sp).strftime('%d/%m/%Y %H:%M')}\n---"]
    lista_dados = []

    for _, row in df_lista.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_msg.append(msg)
        if dados: lista_dados.append(dados)

    if lista_dados:
        atualizar_planilha_excel(lista_dados)
        enviar_mensagem_telegram("\n".join(corpo_msg))
        # Opcional: Descomente a linha abaixo se quiser receber o arquivo TODA HORA
        # enviar_arquivo_telegram()

if __name__ == "__main__":
    executar()
