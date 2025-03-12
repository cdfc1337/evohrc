from flask import Flask, render_template, request, redirect, url_for
import json
import re
import os
from playwright.sync_api import sync_playwright

app = Flask(__name__)

def scrape_data(sala, id_torneio):
    global scraped_data, total_entradas, title  
    # Lista para armazenar os dados extraídos
    scraped_data = []

    with sync_playwright() as p:

        # Step 2: Launch the browser with the user data directory
        browser = p.chromium.launch_persistent_context(
            "playwright_session",
            headless=True,
        )

        # Step 3: Get the first page in the context (or create a new one if needed)
        page = browser.pages[0] if browser.pages else browser.new_page()

        # Step 4: Navigate to the desired page after login
        url = f'https://www.sharkscope.com/#Find-Tournament//networks/{sala}/tournaments/{id_torneio}'
        page.goto(url)

        # Step 5: Wait for the content to load (ensure table rows are present)
        page.wait_for_selector('[id^="jqg"] > td:nth-child(5)', timeout=20000)  # Wait until the elements are available
        
        # Loop for scraping until a '-' is found in the data
        while True:
            # Extract data using the CSS selector
            elements = page.locator('[id^="jqg"] > td:nth-child(5)')
            data = elements.all_text_contents()  # Get all matching elements' inner text

            # Save the extracted data into the list
            if data:
                for text in data:
                    scraped_data.append(text.strip())  # Add each item to the list

            # Check if any of the data contains a '-'
            if any('-' in item for item in data):
                #print("Found '-' in data. Stopping the loop.")
                break  # Stop the loop if '-' is found in any of the data

            # Find the "Next Page" button with a specific id (e.g., last one)
            buttons = page.locator('[role="button"][title="Next Page"]')  # Locator for multiple buttons
            button_count = buttons.count()  # Get the count of matching elements

            if button_count > 0:
                # If there are multiple buttons, click the last one or choose based on your criteria
                button_id = buttons.nth(button_count - 1).get_attribute('id')  # Get the ID of the last button
                #print(f"Dynamic button ID: {button_id}") #Print ID do button Next Page
                
                # Use the dynamic ID to click the button
                page.wait_for_selector(f'#{button_id}', state='visible', timeout=20000)
                page.locator(f'#{button_id}').click()
                
                # Step 8: Wait for the content to load after clicking (ensure elements are updated)
                page.wait_for_selector('[id^="jqg"] > td:nth-child(5)', timeout=20000)  # Wait again for the table content to appear
            else:
                print("No matching buttons found.")
                break  # Stop if there are no "Next Page" buttons available
        
        global total_entradas, title #Get 
        title = page.locator('.tournament-header-table td').nth(0).inner_text().strip()
        entrants_text = page.locator('.tournament-info td:nth-child(4)').inner_text().strip().split(':')[1] if 'Entrants:' in page.locator('.tournament-info td:nth-child(4)').inner_text().strip() else 'N/A'

        # Extração dos números usando expressões regulares
        match = re.match(r"(\d+)\s*\(\+(\d+)\s*Reentries\)", entrants_text)

        if match:
            # Pegamos os valores extraídos
            entrants = int(match.group(1))  
            reentries = int(match.group(2)) 
            total_entradas = entrants + reentries 
        else:
            # Caso não tenha reentries, apenas usamos o número de entrants
            entrants = int(re.search(r"\d+", entrants_text).group(0))
            total_entradas = entrants         

        # Step 9: Close the browser context
        browser.close()

        # Return the data
        return scraped_data, total_entradas, title

def extrair_valores(lista_pagamentos):
    global bounties, dicionario_com_bounties, dicionario_sem_bounties

    pattern = r'[€$]([\d,\.]+)\s*(?:\(ticket\))?\s*\(Bounties:\s*[€$]([\d,\.]+)\)'
    regular = []
    bounties = []

    for texto in lista_pagamentos:
        # Remover vírgulas
        texto = texto.replace(',', '')
        # Encontrar as correspondências
        match = re.findall(pattern, texto)
        if match:
            # Extrair valores numéricos
            regular.append(float(match[0][0]))  # Primeiro valor
            bounties.append(float(match[0][1]))  # Segundo valor (Bounties)
        else:
            # Caso não haja Bounties, procurar apenas o valor regular
            regular_match = re.search(r'[€$]([\d\.]+)', texto)
            if regular_match:
                regular.append(float(regular_match.group(1)))
                bounties.append(0.0)  # Não há Bounties

    totais_com_duas_casas = [round(i, 2) for i in [a - b for a, b in zip(regular, bounties)]] #subtraí valor de bounties a valor regular
    dicionario_com_bounties = {index + 1: valor for index, valor in enumerate(totais_com_duas_casas) if valor != 0}
    #print(dicionario_com_bounties)
    dicionario_sem_bounties = {}
    ultimo_valor = float('inf')  # Inicialmente menor que qualquer número

    for index, valor in enumerate(regular, start=1):  # start=1 para começar do índice 1
        if valor < ultimo_valor:
            dicionario_sem_bounties[index] = valor
            ultimo_valor = valor  # Atualiza o último valor
    dicionario_sem_bounties[len(regular)] = ultimo_valor

    return bounties, dicionario_com_bounties, dicionario_sem_bounties

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def escreve_estrutura_vanila(dicionario, title, fichas_iniciais, total_entradas):
    structured_dict = {
    "name": "/",
    "folders": [],
    "structures": [
        {
            "name": title,
            "chips": fichas_iniciais*total_entradas,  # Valor vazio ou `None` no Python
            "prizes": dicionario,  # Inserindo o dicionário de "chave: valor"
        }
    ]
}
    safe_title = sanitize_filename(title)
    with open(f"{safe_title}.json", "w",  encoding="utf-8") as file:
        json.dump(structured_dict, file, indent=2, ensure_ascii=False)

def escreve_estrutura_pko(dicionario, title, fichas_iniciais, total_entradas):
    structured_dict = {
    "name": "/",
    "folders": [],
    "structures": [
        {
            "name": title,
            "bountyType": "PKO",
            "progressiveFactor": 0.5,
            "chips": fichas_iniciais*total_entradas,  # Valor vazio ou `None` no Python
            "prizes": dicionario,  # Inserindo o dicionário de "chave: valor"
        }
    ]
}
    safe_title = sanitize_filename(title)
    with open(f"{safe_title}.json", "w",  encoding="utf-8") as file:
        json.dump(structured_dict, file, indent=2, ensure_ascii=False)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        sala = request.form["sala"]
        id_torneio = int(request.form["id_torneio"])
        fichas_iniciais = int(request.form["fichas_iniciais"])

        scraped_data, total_entradas, title = scrape_data(sala, id_torneio)
        bounties, dicionario_com_bounties, dicionario_sem_bounties = extrair_valores(scraped_data)
        safe_title = sanitize_filename(title)

        if sala == '888Poker%28ES-PT%29':
            escreve_estrutura_vanila(dicionario_sem_bounties, title, fichas_iniciais, total_entradas)
        else:
            if all(items == 0 for items in bounties):
                escreve_estrutura_vanila(dicionario_sem_bounties, title, fichas_iniciais, total_entradas)
            else:
                escreve_estrutura_pko(dicionario_com_bounties, title, fichas_iniciais, total_entradas)
        return redirect(url_for("success", filename=f"{safe_title}.json"))

    salas_disponiveis = [
        {'codigo': '888Poker%28ES-PT%29', 'nome': '888Poker(ES-PT)'},
        {'codigo': 'PokerStars(FR-ES-PT)', 'nome': 'PokerStars(FR-ES-PT)'},
        {'codigo': 'Winamax.fr', 'nome': 'Winamax'},
        {'codigo': 'GGNetwork', 'nome': 'GGPoker'},
        {'codigo': 'WPN', 'nome': 'WPN'},
        {'codigo': 'PokerStars', 'nome': 'PokerStars'}
    ]
    return render_template("index.html", salas=salas_disponiveis)

@app.route("/success/<filename>")
def success(filename):
    return f"Arquivo gerado com sucesso: {filename}"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # Default to 5000 if PORT is not set
    app.run(host="0.0.0.0", port=port, debug=True)


