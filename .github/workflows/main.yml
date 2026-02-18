name: Monitoramento de barragens

on:
  schedule:
    - cron: "0 * * * *"   # Executa de 1 em 1 hora
  workflow_dispatch:      # Permite rodar manual pelo botão

jobs:
  executar:
    runs-on: ubuntu-latest
    permissions:
      contents: write     # Permissão para o robô salvar arquivos no seu GitHub
      
    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Instalar dependências
        run: pip install pandas requests openpyxl

      - name: Executar script principal
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          CHAT_ID: ${{ secrets.CHAT_ID }}
        run: python main.py

      - name: Persistir dados na nuvem (GitHub)
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add monitoramento_chuvas.xlsx
          git commit -m "Atualização horária automática [skip ci]" || echo "Sem alterações"
          git push
