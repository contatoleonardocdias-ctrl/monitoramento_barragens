import requests
import os
import pandas as pd
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from datetime import datetime, timedelta, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== CONFIGURAÇÕES ====================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ARQUIVO = "barragens.csv"
ARQUIVO_EXCEL = "monitoramento_chuvas.xlsx"

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def atualizar_planilha_excel(novos_dados):
    if os.path.exists(ARQUIVO_EXCEL):
        try:
            df_bruta = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Base Bruta")
            df_bruta = pd.concat([df_bruta, pd.DataFrame(novos_dados)], ignore_index=True)
        except:
            df_bruta = pd.DataFrame(novos_dados)
    else:
        df_bruta = pd.DataFrame(novos_dados)

    df_bruta['Data_dt'] = pd.to_datetime(df_bruta['Data'], dayfirst=True)
    df_bruta['Mês'] = df_bruta['Data_dt'].dt.strftime('%B / %Y')
    aba_resumo = df_bruta.groupby(['Barragem', 'Mês'])['Precipitacao (mm)'].sum().reset_index()
    
    with pd.ExcelWriter(ARQUIVO_EXCEL, engine='openpyxl') as writer:
        df_bruta.drop(columns=['Data_dt', 'Mês']).to_excel(writer, sheet_name="Base Bruta", index=False)
        aba_resumo.to_excel(writer, sheet_name="Resumo Mensal", index=False)

def enviar_telegram(mensagem, foto=None):
    if not TOKEN or not CHAT_ID: return
    if foto:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        files = {'photo': ('grafico.png', foto, 'image/png')}
        payload = {"chat_id": str(CHAT_ID).strip(), "caption": mensagem, "parse_mode": "Markdown"}
        try: session.post(url, data=payload, files=files, timeout=30)
        except: pass
    else:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": str(CHAT_ID).strip(), "text": mensagem, "parse_mode": "Markdown"}
        try: session.post(url, data=payload, timeout=20)
        except: pass

def gerar_grafico_mensal():
    if not os.path.exists(ARQUIVO_EXCEL): return None
    try:
        df = pd.read_excel(ARQUIVO_EXCEL, sheet_name="Base Bruta")
        df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True)
        
        # Lógica Retrocedente: Pega o mês anterior à data atual do sistema
        hoje = datetime.now(timezone(timedelta(hours=-3)))
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        
        mes_alvo = ultimo_dia_mes_anterior.month
        ano_alvo = ultimo_dia_mes_anterior.year
        
        df_mes = df[(df['Data_dt'].dt.month == mes_alvo) & (df['Data_dt'].dt.year == ano_alvo)].copy()

        if df_mes.empty: return None

        plt.figure(figsize=(10, 5))
        for barragem in df_mes['Barragem'].unique():
            sub = df_mes[df_mes['Barragem'] == barragem].sort_values('Data_dt')
            diario = sub.groupby(sub['Data_dt'].dt.date)['Precipitacao (mm)'].sum()
            plt.plot(diario.index, diario.values, marker='o', label=barragem)

        plt.title(f"Precipitação Mensal Retrocedente - {mes_alvo:02d}/{ano_alvo}")
        plt.xlabel("Dia")
        plt.ylabel("Chuva (mm)")
        plt.legend(loc='best')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()

        img_data = io.BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)
        plt.close()
        return img_data
    except:
        return None

def verificar_clima(nome, lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={round(lat, 4)}&longitude={round(lon, 4)}&current=precipitation,is_day,cloud_cover,temperature_2m&hourly=precipitation&timezone=America%2FSao_Paulo"
    try:
        time.sleep(3) 
        response = session.get(url, timeout=45) 
        res = response.json()
        if "error" in res: return f"📍 *{nome.upper()}*\n❌ Erro na API\n", None
        curr = res.get("current", {})
        chuva_agora = curr.get("precipitation", 0.0)
        temp = curr.get("temperature_2m", 0.0)
        is_day = curr.get("is_day", 1)
        nuvens = curr.get("cloud_cover", 0)
        precip_h = res.get("hourly", {}).get("precipitation", [])
        chuva_prevista = precip_h[1] if len(precip_h) > 1 else 0.0
        agora = datetime.now(timezone(timedelta(hours=-3)))
        dados_planilha = {
            "Data": agora.strftime('%d/%m/%Y'), "Hora": agora.strftime('%H:%M'),
            "Barragem": nome.upper(), "Precipitacao (mm)": chuva_agora, "Temp (C)": temp
        }
        emoji = "☁️" if nuvens > 70 else ("☀️" if is_day and nuvens < 25 else "⛅" if is_day else "🌙" if nuvens < 25 else "☁️")
        status = (f"⚠️ **ALERTA DE CHUVA**\n🌧️ Agora: {chuva_agora:.1f}mm\n🔮 Próxima: {chuva_prevista:.1f}mm" 
                  if (chuva_agora > 0 or chuva_prevista > 0) else f"{emoji} Sem chuva")
        return f"📍 *{nome.upper()}*\n🌡️ {temp:.1f}°C\n{status}\n", dados_planilha
    except: return f"📍 *{nome.upper()}*\n❌ Falha\n", None

def executar():
    if not os.path.exists(ARQUIVO): return
    df_loc = pd.read_csv(ARQUIVO)
    agora = datetime.now(timezone(timedelta(hours=-3)))
    corpo = ["**🛰️ RELATÓRIO DE BARRAGENS**", f"⏰ {agora.strftime('%d/%m/%Y %H:%M')}\n"]
    
    dados_excel = []
    for _, row in df_loc.iterrows():
        msg, dados = verificar_clima(str(row['nome']), float(row['lat']), float(row['long']))
        corpo.append(msg)
        if dados: dados_excel.append(dados)

    if dados_excel: atualizar_planilha_excel(dados_excel)
    
    # LÓGICA AUTOMÁTICA: Se for dia 1, gera o gráfico do mês que passou.
    foto_grafico = None
    if agora.day == 1:
        foto_grafico = gerar_grafico_mensal()
        if foto_grafico:
            corpo.insert(0, "📊 **FECHAMENTO MENSAL RETROcedente**")

    enviar_telegram("\n".join(corpo), foto=foto_grafico)

if __name__ == "__main__":
    executar()
