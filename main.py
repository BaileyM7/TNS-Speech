import os
import sys
import csv
import getopt
import logging
from openai import OpenAI
from datetime import datetime
from email_utils import send_summary_email
from url_functions import getKey, parse_test_urls, process_speeches, write_press_releases_to_csv

"""
Author: Bailey Malota
Last Updated: Jul 18 2025
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
    
    # formatting the summary email to be sent
    end_time = datetime.now()
    elapsed = str(end_time - start_time).split('.')[0]
    

    if test_run:
        urls = parse_test_urls(test_input_path)
        output = process_speeches(urls)
        write_press_releases_to_csv(output_path, output)


    summary = f"""
    Load Version 1.0.0 07/18/2025

    Passed Parameters: {' -t' if test_run else ''} {' -p' if production_run else ''}

    Grants Loaded: {processed}

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