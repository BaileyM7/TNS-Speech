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

# proccesses each url and returns a header and body text
def process_speeches(urls, is_test):
    client_sync = OpenperplexSync(getKey())
    outputs = []

    #sync
    for n in range(len(urls)):
        # print(urls[n])
        
        if is_test:
            prompt = (
                "Write a headline and a 300-word press release based only on the content of the following speech.\n\n"
                "Strictly follow these rules:\n"
                "- DO NOT include any introductory lines such as 'FOR IMMEDIATE RELEASE', 'CONTACT', or press contact names or emails.\n"
                "- DO NOT include datelines like 'Washington, D.C.' or dates at the top.\n"
                "- DO NOT mention the city, state, or any location unless it is explicitly discussed in the speech itself.\n"
                "- Focus only on the core message or argument made in the speech.\n"
                "- Begin the output with the headline, followed by a newline, then the body."
            )
        else:
            prompt = (
                f"Write a headline that includes the agency name: {urls[n][2]}, followed by a 300-word press release based only on the content of the following speech.\n\n"
                "Strictly follow these rules:\n"
                "- DO NOT include any introductory lines such as 'FOR IMMEDIATE RELEASE', 'CONTACT', or press contact names or emails.\n"
                "- DO NOT include datelines like 'Washington, D.C.' or dates at the top.\n"
                "- DO NOT mention the city, state, or any location unless it is explicitly discussed in the speech itself.\n"
                "- Focus only on the core message or argument made in the speech.\n"
                "- Begin the output with the headline, followed by a newline, then the body."
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
            outputs.append((None, None)) 

        # getting both the headline and body
        headline_raw = parts[0]
        body_raw = parts[1]

        today_date = get_body_date()
        press_release = f"WASHINGTON, {today_date} -- {body_raw.strip()}"
        press_release += f"\n\n* * *\n\nView speech here: {urls[n]}."

        # getting rid of stray input from gpt and turning all text into ASCII charectors for DB
        headline = clean_text(headline_raw)
        headline = cleanup_text(headline)

        press_release = clean_text(press_release)
        press_release = cleanup_text(press_release)
        
        # making the filename for the speeches
        filename = generate_filename(urls[n])

        # append headline, press_release
        if is_test:
            outputs.append((filename, headline, press_release))
        else:
            outputs.append((filename, headline, press_release, urls[n][1]))

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
