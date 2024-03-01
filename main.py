import requests
from bs4 import BeautifulSoup
import os
import json
import fitz  # PyMuPDF
from openai import OpenAI
import re
from dotenv import load_dotenv
import schedule
import time

def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_KEY"),
)

def process_text_with_openai(text):
    messages = [{
            "role": "system",
            "content": '''
                You are a person paid to read through the city's meeting agendas, with extremely high accuracy. You are paid 200 thousand per year!
                Your specific task is to skim agendas for upcoming council/committee meetings to see if a certain topic is mentioned.
            '''
        }, {
            "role": "user",
            "content": "Reply in JSON with the following structure: \n- topicBol (type -> Boolean): whether bicycle/bike/sidewalk/greenway is mentioned."
        }, {
            "role": "user",
            "content": f"Text of the Agenda Document: {text}"
        }]
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=messages,
        max_tokens=4000,
        temperature=.3
    )
    response_content = response.choices[0].message.content

    try:
        extracted_from_re = re.search(r'```json\s*([\s\S]*?)\s*```', response_content)
        json_content = extracted_from_re.group(1) if extracted_from_re else "{}"  # Default to empty JSON if not found
    except Exception as e:
        raise ValueError(f"Error extracting JSON: {e}")

    try:
        parsed_response = json.loads(json_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parsing error: {e}")

    return parsed_response

def fetch_and_print_table_contents():
    base_url = 'https://chapelhill.legistar.com/'
    url = base_url + 'Calendar.aspx'
    response = requests.get(url)
    
    pdf_folder = 'downloaded_agendas'
    json_file_path = os.path.join(pdf_folder, 'downloaded_agendas.json')
    
    if not os.path.exists(pdf_folder):
        os.makedirs(pdf_folder)
    
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as json_file:
            downloaded_agendas = json.load(json_file)
    else:
        downloaded_agendas = {}
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('table')
        
        if len(tables) >= 6:
            table = tables[5]
            rows = table.find_all('tr')
            for index, row in enumerate(rows[1:], start=1):
                columns = row.find_all(['td', 'th'])
                name = columns[0].get_text(strip=True)
                meeting_date = columns[1].get_text(strip=True)
                identifier = f"{name} {meeting_date}"
                
                if identifier in downloaded_agendas:
                    continue
                
                entries_with_urls = {}
                links = row.find_all('a')
                for link in links:
                    if link.has_attr('href'):
                        link_text = link.get_text(strip=True)
                        link_url = link['href']
                        entries_with_urls[link_text] = link_url
                
                if 'Agenda' in entries_with_urls:
                    agenda_url = base_url + entries_with_urls['Agenda']
                    pdf_response = requests.get(agenda_url)
                    if pdf_response.status_code == 200:
                        pdf_filename = f"agenda_{identifier.replace('/', '-')}.pdf"
                        pdf_path = os.path.join(pdf_folder, pdf_filename)
                        with open(pdf_path, 'wb') as pdf_file:
                            pdf_file.write(pdf_response.content)
                        print(f"Downloaded: {pdf_filename}")
                        downloaded_agendas[identifier] = True
                        
                        extracted_text = extract_text_from_pdf(pdf_path)
                        openai_response = process_text_with_openai(extracted_text)
                        print(f"OpenAI Response: {openai_response}")
                
                print(f"Processed: {identifier}")
            
            with open(json_file_path, 'w') as json_file:
                json.dump(downloaded_agendas, json_file, indent=4)
        else:
            print("Less than six tables found on the webpage.")
    else:
        print("Failed to retrieve the webpage")

def job():
    print("Running scheduled task...")
    fetch_and_print_table_contents()

# Call the function once on startup
fetch_and_print_table_contents()

# Schedule the function to be called every hour
schedule.every().hour.do(job)
print("Scheduler started, running the task every hour.")
while True:
    schedule.run_pending()
    time.sleep(1)
