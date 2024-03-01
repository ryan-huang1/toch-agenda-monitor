import requests
from bs4 import BeautifulSoup
import os
import json
import fitz  # PyMuPDF
from openai import OpenAI
import re
from dotenv import load_dotenv
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
    # Example function to send text to OpenAI's API
    # Modify according to your specific use case
    messages = [{
            "role": "system",
            "content": '''
                You a person paid to read through the city's meeting agendas, with extremely high acuracy. You are paid 200 thousand per year!
                You specific task is to skim agendas for upcoming council/committee meetings if a certain topic is mentioned
            '''
        }, {
            "role": "user",
            "content": [{
                "type": "text",
                "text": '''
                    Reply in JSON with the following structure: 
                    \n- topicBol (type -> Boolean): is bicycle/bike/sidewalk/greenway is mentioned 
                    \nHere's an example output: 
                    {
                    "topicBol": true
                    }
                '''
            }]
        }, {
            "role": "user",
            "content": [{
                "type": "text",
                "text": f'Text of the Agenda Document: {text}'
            }]
        }]
    # Attempt to call the API with the constructed messages list
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=messages,
        max_tokens=4000,
        temperature=.3
    )
    response_content = response.choices[0].message.content

    try:
        extracted_from_re = re.search(r'```json\s*([\s\S]*?)\s*```', response_content)
        json_content = extracted_from_re.group(1)
    except:
        json_content = response_content

    print(json_content)
    try:
        parsed_response = json.loads(json_content)
        print('parced sucessfully')
    except json.JSONDecodeError as e:
        print("JSON parsing error")
        raise ValueError(f"JSON parsing error: {e}")

    return parsed_response

def fetch_and_print_table_contents():
    base_url = 'https://chapelhill.legistar.com/'
    url = base_url + 'Calendar.aspx'
    response = requests.get(url)
    
    pdf_folder = 'downloaded_agendas'
    json_file_path = os.path.join(pdf_folder, 'downloaded_agendas.json')
    
    # Ensure the directory exists
    if not os.path.exists(pdf_folder):
        os.makedirs(pdf_folder)
    
    # Load or initialize the tracking dictionary
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
                        
                        # Extract text from the PDF
                        extracted_text = extract_text_from_pdf(pdf_path)
                        # Process the extracted text with OpenAI
                        openai_response = process_text_with_openai(extracted_text)
                        print(f"OpenAI Response: {openai_response}")
                
                print(f"Processed: {identifier}")
            
            with open(json_file_path, 'w') as json_file:
                json.dump(downloaded_agendas, json_file, indent=4)
            
            print("\n\n")
        else:
            print("Less than six tables found on the webpage.")
    else:
        print("Failed to retrieve the webpage")

if __name__ == "__main__":
    fetch_and_print_table_contents()
