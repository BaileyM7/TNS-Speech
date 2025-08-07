import os
import sys
import csv
import getopt
import logging
from openai import OpenAI
from datetime import datetime
from email_utils import send_summary_email
from url_functions import getKey, parse_csv, process_speeches, write_press_releases_to_csv
from db_functions import get_db_connection, get_121_speech_urls, insert_press_release

"""
Author: Bailey Malota
Last Updated: Aug 4 2025
"""

"""
Each Speech is packaged with its AgencyName, Category, and URL

The category reffers to the location of where the authors name is located.

Category Labels:

A: The author's name is in the header
B: The author's name is in the body text
C: The author's name is in the end of the text
E: No Author available
"""
# getting the api key
client = OpenAI(api_key=getKey())

# setting up the Logging functionality
logfile = f"scrape_log.{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M:%S",
    filename=logfile,
    filemode="w"
)

# more logging setup
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
console.setFormatter(formatter)
logging.getLogger("").addHandler(console)

# main runner
def main(argv):
    # setting up email summary variable
    start_time = datetime.now()
    processed = 0
    skipped = 0
    dups = 0
    test_run = False
    production_run = False
    test_input_path = "test_urls.csv"
    output_path = "speech_output.csv"

    # gettings options
    try:
        opts, args = getopt.getopt(argv, "pt")
    except getopt.GetoptError:
        print("Usage: -p -t")
        sys.exit(1)

    # settings get opt variables
    for opt, _ in opts:
        if opt == "-p":
            production_run = True
        elif opt == "-t":
            test_run = True    

    if test_run:
        results = parse_csv(test_input_path)
        output = process_speeches(results, True)
        write_press_releases_to_csv(output_path, output)

    if production_run:
        urls_preprocesses = get_121_speech_urls()
        urls = []

        # tallying skips based off of whether the loaders put urls properly into the coder for me to gather
        for url in urls_preprocesses:
            if "https://" in url:
                urls.append(url)
            else:
                skipped += 1
        
        outputs = process_speeches(urls, False)

        get_db_connection()
        
        # parsing through and inserting each output to the DB
        for filename, headline, body, a_id in outputs:
            if not filename or not headline or not body:
                logging.warning("Skipping incomplete record.")
                skipped += 1
                continue

            if insert_press_release(filename, headline, body, a_id) == False:
                dups += 1
            else:
                processed += 1

    # formatting the summary email to be sent
    end_time = datetime.now()
    elapsed = str(end_time - start_time).split('.')[0]

    summary = f"""
    Load Version 1.0.4 08/7/2025

    Passed Parameters: {' -t' if test_run else ''} {' -p' if production_run else ''}

    Speches Loaded: {processed}
    Duplicates Found: {dups}
    Speeches Skipped: {skipped}

    Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
    End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
    Elapsed Time: {elapsed}
    """
    
    logging.info(summary)
    logging.shutdown()
    send_summary_email(summary, logfile)

    # runs main the the args
if __name__ == "__main__":
    main(sys.argv[1:])