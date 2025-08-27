import re
import csv
import time
import logging
import platform
from openai import OpenAI
from datetime import datetime
from urllib.parse import urlparse
from cleanup_text import cleanup_text, clean_text
from openperplex import OpenperplexSync


# gets the api keys
def getKey():
    """Retrieves the OpenAI API key from a file."""
    try:
        with open("utils/openperplex.txt", "r") as file:
            return file.readline().strip()
    except FileNotFoundError:
        logging.info("File not found!")
    except PermissionError:
        logging.info("You don't have permission to access this file.")
    except IOError as e:
        logging.info(f"An I/O error occurred: {e}")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except:
        return False

def extract_clean_agency_name(raw_name):
    match = re.match(r"^(.*?)(\[|\(|:|$)", raw_name.strip())
    return match.group(1).strip() if match else raw_name.strip()

def parse_csv(file_path):
    results = []
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter='|', skipinitialspace=True)

        # Strip leading/trailing whitespace from header field names
        reader.fieldnames = [field.strip() for field in reader.fieldnames]

        for row in reader:
            # Skip completely empty or malformed rows
            if row is None or not any(row.values()):
                continue

            raw_agency = row.get('AgencyName', '').strip()
            author = row.get('Author', '').strip()
            title = row.get('Title', '').strip()  # <-- New column
            url = row.get('Url', '').strip()

            # Skip invalid author/title values
            if not author or author.upper() == 'NA' or not title or title.upper() == 'NA':
                results.append((None, None, None, None))
                continue

            # Skip invalid URL
            if not is_valid_url(url):
                results.append((None, None, None, None))
                continue

            # Clean agency name
            agency = extract_clean_agency_name(raw_agency)

            # Append title between agency and url
            results.append((agency, author, title, url))

    return results


# makes the date that goes after "WASHINGTON --"
def get_body_date():
    today = datetime.today()
    month = today.strftime('%B') 
    short_month = today.strftime('%b')
    formatted_month = month if len(month) <= 5 else short_month + "."
    day_format = '%-d' if platform.system() != 'Windows' else '%#d'
    return f"{formatted_month} {today.strftime(day_format)}"

def generate_filename(url):
    """
    Generates a filename of the form:
    $H YYMMDD-speech-{domain_prefix}, where domain_prefix is the part between '//' and first '.'
    """
    date = datetime.now().strftime("%y%m%d")
    parsed = urlparse(url)
    domain_parts = parsed.netloc.split('.')

    # Skip "www" if it's present
    if domain_parts[0] == "www":
        clean_domain = domain_parts[1]
    else:
        clean_domain = domain_parts[0]

    return f"$H {date}-speech-{clean_domain}"


# checks the output from ai prompt to look for malformed outputs containing peices of the original prompt
def check_news_output(output):
    # parts of the prompt that shoulve been replaces
    forbidden_phrases = ["full agency name","speaker title","speaker full name", "agency name"]
    
    # making the output lwocase to make sure case sensitivity doesnt matter
    output_lower = output.lower()
    
    # return fasle if output isnt correct
    for phrase in forbidden_phrases:
        if phrase in output_lower:
            return False
    
    return True


# proccesses each url and returns a header and body text
def process_speeches(results, is_test):
    from openperplex import OpenperplexSync  # Assuming this is your client
    client_sync = OpenperplexSync(getKey())
    outputs = []

    # Process each (agency, author, url) tuple
    for agency, author, title, url in results:
        if not agency or not author or not url:
            continue  # Skip invalid entries

        # Dynamically insert agency and author into the rules for better grounding
        prompt = f"""
        Write a press release based on a speech delivered by {author} from {agency}. Follow these rules:

        Headline:
        - Write a single-line headline.
        - It must include the speaker’s full name and the **abbreviated agency name** (e.g., "SEC" instead of "Securities and Exchange Commission").

        Press Release Body:
        - The first sentence must begin exactly like this (replacing with the real values):
        “{agency} {title} {author} issued the following statement,”
        - This sentence must **flow directly into the paragraph**, not be isolated on its own line.
        - Do NOT include any introductory lines such as “FOR IMMEDIATE RELEASE,” “CONTACT,” or press contact info.
        - Do NOT include any datelines like “Washington, D.C.” or any location unless it appears in the speech.
        - Abbreviate “United States” as “U.S.” unless it is part of an official name.
        - After the first sentence, summarize the speech’s key points clearly and professionally.
        - The speaker may only be named in the first paragraph.

        - Write two to three structured paragraphs total.
        - Each paragraph must include at least one **direct quote** from the speech.
        - Do not reuse the speaker’s name or title after the first sentence.
        - Maintain a clean, professional tone and avoid bullet points, headers, or section labels.

        Input Information:
        Speaker Name: {author}
        Agency: {agency}
        Title: {title}

        Analyze the length of the speech text. Then, write a press release that is approximately **half the word count** of the speech.
        """

        try:
            response = client_sync.query_from_url(
                url=url,
                query=prompt,
                model='gpt-4o-mini',
                response_language="en",
                answer_type="text",
            )

        except Exception as e:
            print(f"Error processing {url}: {e}")
            outputs.append((None, None, None))
            continue  

        time.sleep(5)
        
        # Defensive check
        if not isinstance(response, dict) or 'llm_response' not in response:
            logging.warning(f"Malformed response for {url}")
            outputs.append((None, None, None))
            continue

        text = response.get("llm_response", "")

        # getting rid of common gpt hallicination issues
        text = text.replace("Press Release Body:", "").replace("Headline:", "")

        parts = text.split('\n', 1)

        # Validate format
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            logging.info(f"Headline or body was not parsed correctly for {url}")
            outputs.append((None, None, None))
            continue

        # getting both the headline and body
        headline_raw = parts[0]
        body_raw = parts[1]

        today_date = get_body_date()
        press_release = f"WASHINGTON, {today_date} -- {body_raw.strip()}"
        press_release += f"\n\n* * *\n\nView speech here: {url}"

        # getting rid of stray input from gpt and turning all text into ASCII charectors for DB
        headline = clean_text(headline_raw)
        headline = cleanup_text(headline)

        press_release = clean_text(press_release)
        press_release = cleanup_text(press_release)
        
        # making the filename for the speeches
        filename = generate_filename(url)

        # checking to make sure that output is correct
        if check_news_output(press_release) and check_news_output(headline):
            outputs.append((filename, headline, press_release))

        # if output is invalid, add none none none so that it is counted as skipped in summary email
        else:
            outputs.append((None, None, None))

        # print(headline)
        # print(press_release)
        
    # return a list of tuples comtaining each headline and press release pair
    return outputs


def write_press_releases_to_csv(output_path, data):
    # Writes speech processing results to a CSV with columns

    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['filename', 'headline', 'Speech Output'])

        for filename, headline, press_release in data:
            writer.writerow([filename, headline, press_release])
