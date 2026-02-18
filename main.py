import requests
import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

def atualizar_planilha_excel(novos_dados):
    """Salva os dados no Excel com Base Bruta e Resumo Mensal"""
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

    df_salvar_bruta = df_bruta.drop(columns=['Data_dt', 'Mês'])
    
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_salvar_bruta.to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

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
        f"&current=precipitation,is_day,cloud_cover,temperature_2m"
        f"&hourly=precipitation"
        f"&timezone=America%2FSao_Paulo"
    )
    try:
        res = requests.get(url, timeout=25).json()
        
        chuva_agora = res["current"].get("precipitation", 0.0)
        temp = res["current"].get("temperature_2m", 0.0)
        chuva_prevista = res["hourly"]["precipitation"][1]
        is_day = res["current"]["is_day"]
        nuvens = res["current"]["cloud_cover"]

        fuso_sp = timezone(timedelta(hours=-3))
        agora = datetime.now(fuso_sp)

        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'),
            "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(),
            "Precipitacao (mm)": chuva_agora,
            "Temp (C)": temp
        }

        if chuva_agora > 0 or chuva_prevista > 0:
            status_formatado = (
                f"⚠️ **ALERTA DE CHUVA**\n"
                f"🌡️ **Temp:** {temp:.1f}°C\n"
                f"🌧️ **Tempo Real:** {chuva_agora:.1f}mm agora / {chuva_prevista:.1f}mm esperado"
            )
        else:
            if nuvens > 70:
                emoji = "☁️"
            else:
                emoji = "☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️"
            
            # Temperatura incluída aqui para quando não estiver chovendo
            status_formatado = f"{emoji} **{temp:.1f}°C** Sem chuva"

        return f"📍 *{nome.upper()}*\n{status_formatado}\n", dados_planilha
    except Exception:
        return f"📍 *{nome.upper()}*\n❌ Erro na consulta\n", None

def executar():
    fuso_sp = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_sp)
    
    if not os.path.exists(ARQUIVO): return

    df = pd.read_csv(ARQUIVO)
    corpo_mensagem = ["**🛰️ RELATÓRIO DE BARRAGENS**", f"⏰ {agora.strftime('%d/%m/%Y %H:%M')}\n"]
    
    dados_para_excel = []
    for _, row in df.iterrows():
        msg, dados = verificar_clima(row['nome'], row['lat'], row['long'])
        corpo_mensagem.append(msg)
        if dados:
            dados_para_excel.append(dados)

    if dados_para_excel:
        atualizar_planilha_excel(dados_para_excel)

    enviar_telegram("\n".join(corpo_mensagem))

if __name__ == "__main__":
    executar()
