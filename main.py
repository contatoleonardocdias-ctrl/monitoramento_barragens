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
    """Gerencia as abas 'Base Bruta' e 'Total Dia'"""
    fuso_sp = timezone(timedelta(hours=-3))
    hoje_str = datetime.now(fuso_sp).strftime('%d/%m/%Y')

    # 1. Carregar Base Bruta existente ou criar nova
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            with pd.ExcelFile(ARQUIVO_EXCEL) as xls:
                df_bruta = pd.read_excel(xls, "Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except Exception:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    # 2. Gerar Aba de Acumulado Diário (Soma de tudo que ocorreu hoje)
    df_bruta['Data'] = df_bruta['Data'].astype(str)
    df_hoje = df_bruta[df_bruta['Data'] == hoje_str]
    
    aba_acumulado = df_hoje.groupby('Barragem')['Precipitacao (mm)'].sum().reset_index()
    aba_acumulado.columns = ['Barragem', 'Total Acumulado Hoje (mm)']
    aba_acumulado['Ultima Leitura'] = datetime.now(fuso_sp).strftime('%H:%M')

    # 3. Salvar no arquivo com motor openpyxl
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_acumulado.to_excel(writer, sheet_name="Total Dia", index=False)

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=25)
    except:
        pass

def verificar_clima(nome, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=precipitation,temperature_2m,is_day,cloud_cover"
        f"&timezone=America%2FSao_Paulo"
    )
    
    try:
        res = requests.get(url, timeout=25).json()
        curr = res.get("current", {})
        chuva = curr.get("precipitation") or 0.0
        temp = curr.get("temperature_2m")
        
        fuso_sp = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_sp)
        
        # Dados para a planilha
        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'),
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(),
            "Precipitacao (mm)": chuva,
            "Temp (C)": temp
        }

        # Texto para o Telegram
        status = f"🌡️ **{temp}°C** | 🌧️ **Agora:** {chuva}mm" if chuva > 0 else f"🌡️ **{temp}°C** | Sem chuva"
        msg_telegram = f"📍 *{nome.upper()}*\n{status}\n"
        
        return msg_telegram, dados_planilha
    except:
        return f"📍 *{nome.upper()}*\n❌ Erro na leitura\n", None

def executar():
    if not os.path.exists(ARQUIVO_BARRAGENS):
        print("Arquivo CSV de barragens não encontrado!")
        return

    df_lista = pd.read_csv(ARQUIVO_BARRAGENS)
    fuso_sp = timezone(timedelta(hours=-3))
    agora_str = datetime.now(fuso_sp).strftime('%d/%m/%Y %H:%M')
    
    corpo_msg = [f"🛰️ **RELATÓRIO HORÁRIO**\n⏰ {agora_str}\n---"]
    lista_dados = []

    for _, row in df_lista.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_msg.append(msg)
        if dados:
            lista_dados.append(dados)

    if lista_dados:
        atualizar_planilha_excel(lista_dados)
        enviar_telegram("\n".join(corpo_msg))
        print(f"Sucesso! Planilha atualizada às {agora_str}")

if __name__ == "__main__":
    executar()
