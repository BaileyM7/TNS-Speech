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


# makes the date that goes after "WASHINGTON --"
def get_body_date():
    today = datetime.today()
    month = today.strftime('%B') 
    short_month = today.strftime('%b')
    formatted_month = month if len(month) <= 5 else short_month + "."
    day_format = '%-d' if platform.system() != 'Windows' else '%#d'
    return f"{formatted_month} {today.strftime(day_format)}"


# ran when -t is passed. This will scrape all the urls in the test file like they would come from the DB    
def parse_test_urls(path):
    urls = []
    # opens csv
    with open(path, 'r', encoding='utf-8') as file:
        # only adds urls to the list
        for line in file:
            if "https://" in line:
                urls.append(line.strip())
    return urls

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
def process_speeches(urls, is_test):
    client_sync = OpenperplexSync(getKey())
    outputs = []

    # shared formatting rules 
    rules = (
        "Follow these instructions exactly:\n"
        "- Read the speech and extract the speaker's **full name**, **official title**, and the **full name of the agency they represent**.\n"
        "- Use this information to create the first sentence of the first paragraph using this format (with real values):\n"
        "  '[Agency Name] [Title] [Full Name] issued the following statement'\n"
        "- Do not copy or include placeholder text like 'Full Name' or 'Full Agency Name'. Use the real values from the speech.\n"
        "- The **headline** must include the speaker’s full name and the **abbreviated form of the agency name** (e.g., 'SEC' instead of 'Securities and Exchange Commission').\n"
        "- Do not include any introductory lines such as 'FOR IMMEDIATE RELEASE', 'CONTACT', or press contact information.\n"
        "- Do not add datelines (e.g., 'Washington, D.C.') or dates at the top.\n"
        "- Do not mention a city, state, or location unless it is specifically referenced in the speech content.\n"
        "- Abbreviate 'United States' as 'U.S.' unless part of an official name.\n"
        "- The opening sentence must blend naturally into the first paragraph. Do not isolate it or format it like a title or header.\n"
        "- Continue the paragraph with a summary of the key speech points in a professional tone.\n"
        "- The speaker should only be referenced in the first paragraph. Do not repeat their name or title later.\n"
        "- Write a total of **two to three paragraphs**, and each paragraph must contain at least one **direct quote** from the speech.\n"
        "- Do not insert extra line breaks after the first sentence unless grammatically necessary.\n"
        "- The output must begin with the **headline**, followed by **one newline**, then the full body text."
    )

    # calling gpt api on each speech
    for n in range(len(urls)):
        # print(urls[n])
        
        if is_test:
            prompt = (
                "Write a headline and a 300-word press release based only on the content of the following speech.\n\n"
                f"{rules}"
            )
        else:
            prompt = (
                f"Write a headline that includes both the speaker's full name and their agency: {urls[n][2]}.\n\n"
                "Then write a 300-word press release based only on the content of the following speech.\n\n"
                f"{rules}"
            )

        response = client_sync.query_from_url(
            url= urls[n],
            query=prompt,
            model='gpt-4o-mini',
            response_language="en",
            answer_type="text",

        )

        time.sleep(5)
        
        text = response.get("llm_response", "")
        parts = text.split('\n', 1)

        if len(parts) != 2:
            # TODO: ADD LOG MESSAGE HERE
            logging.info(f"Headline Wasnt Parsed Right")
            outputs.append((None, None, None)) 
            continue

        # getting both the headline and body
        headline_raw = parts[0]
        body_raw = parts[1]

        today_date = get_body_date()
        press_release = f"WASHINGTON, {today_date} -- {body_raw.strip()}"
        press_release += f"\n\n* * *\n\nView speech here: {urls[n]}"

        # getting rid of stray input from gpt and turning all text into ASCII charectors for DB
        headline = clean_text(headline_raw)
        headline = cleanup_text(headline)

        press_release = clean_text(press_release)
        press_release = cleanup_text(press_release)
        
        # making the filename for the speeches
        filename = generate_filename(urls[n])

        # checking to make sure that output is correct
        if check_news_output(press_release) and check_news_output(headline):
            
            # append headline, press_release
            if is_test:
                outputs.append((filename, headline, press_release))
            else:
                outputs.append((filename, headline, press_release, urls[n][1]))

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
        writer.writerow(['filename', 'headline', 'press_release'])

        for filename, headline, press_release in data:
            writer.writerow([filename, headline, press_release])
