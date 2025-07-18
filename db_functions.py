import yaml
import logging
import mysql.connector
from typing import List, Tuple
from datetime import datetime, timedelta

# DB helper
def get_db_connection(yml_path: str = "configs/db_config.yml"):
    """
    Reads YAML credentials (host, user, password, database) and returns an open MySQL connection.
    """
    with open(yml_path, "r") as yml_file:
        cfg = yaml.load(yml_file, Loader=yaml.FullLoader)
    return mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
    )

# gets all data from the 121 speech feilds
# returns it in the form (url, a_id, "agency")
def get_121_speech_urls():
    cutoff = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    """
    Returns [(url, a_id, agency_name), ...] for rows in not_scraped_log
    whose reason_not_scraped = '121 Speech' and timestamp > cutoff.
    """
    query = """
        SELECT
            n.headline          AS url,
            n.a_id              AS a_id,
            a.agency_name       AS agency_name
        FROM not_scraped_log n
        JOIN agencies a ON a.a_id = n.a_id
        WHERE n.reason_not_scraped = '121 Speech'
          AND n.timestamp > %s
        ORDER BY n.timestamp DESC
    """

    conn = cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (cutoff,))
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"Database query failed: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def insert_press_release(filename, headline, body, a_id, uname="T70-Bailey-Spee", dt_id=1, status='D'):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate filename
        check_sql = "SELECT COUNT(*) FROM press_release WHERE filename = %s"
        cursor.execute(check_sql, (filename,))
        if cursor.fetchone()[0] > 0:
            logging.info(f"Duplicate filename, skipping: {filename}")
            return False

        content_date = datetime.now().date()

        insert_sql = """
        INSERT INTO press_release (
            dt_id, headline, content_date, body_txt, status,
            uname, filename, create_date, last_action, a_id
        )
        VALUES (%s, %s, %s, %s, %s,
                %s, %s, NOW(), SYSDATE(), %s)
        """

        cursor.execute(insert_sql, (
            dt_id,
            headline,
            content_date,
            body,
            status,
            uname,
            filename,
            a_id
        ))

        conn.commit()
        logging.info(f"Inserted press release: {filename}")
        return cursor.lastrowid

    except Exception as err:
        logging.error(f"DB insert failed for press release: {err}")
        return None

    finally:
        if conn:
            conn.close()
