import requests
import json
import time
import os
import sys
import psycopg2
import dateutil.parser
from datetime import datetime
from typing import List
from dotenv import load_dotenv
from models import Bookmark

URL = "https://api.raindrop.io/rest/v1/raindrops/0"
MAX_BOOKMARKS_PER_PAGE = 50

SAVE_JSON = "SAVE_JSON"
SAVE_DB = "SAVE_DB"


def get_save_preference():
    if len(sys.argv) > 1:
        pref = sys.argv[1]
        if pref == "db":
            return SAVE_DB
        elif pref == "json":
            return SAVE_JSON

    return SAVE_JSON


def save_bookmarks_in_json_file(bookmarks: List[Bookmark]):
    with open(os.path.join("output", f"all_bookmarks_{int(time.time())}.json"), "w") as out_file:
        json.dump({
            'bookmarks': [vars(bookmark) for bookmark in bookmarks],
            "created_at": datetime.utcnow().isoformat()
        }, out_file)


def get_most_recent_created_at_for_bookmarks(config):
    connection = None
    cursor = None

    print("Fetching 'created_at' of most recent bookmark from database")

    try:
        connection = psycopg2.connect(
            user=config['db_username'], password=config['db_password'], host=config['db_host'], port=config['db_port'])
        cursor = connection.cursor()
        sql_select_query = """SELECT created_at FROM bookmark ORDER BY created_at DESC LIMIT 1"""
        result = cursor.execute(sql_select_query)
        record = cursor.fetchone()

        if record is not None:
            return record[0].replace(tzinfo=None)

    except (Exception, psycopg2.Error) as error:
        print("Failed inserting record into mobile table {}".format(error))
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

    return None


def save_bookmarks_in_db(config, bookmarks, most_recent_created_at_datetime):
    connection = None
    cursor = None

    filtered_bookmarks = bookmarks
    if most_recent_created_at_datetime is not None:
        filtered_bookmarks = list(filter(lambda x: dateutil.parser.parse(
            x.created_at).replace(tzinfo=None) > most_recent_created_at_datetime, bookmarks))

    len_filtered_bookmarks = len(filtered_bookmarks)
    if len_filtered_bookmarks > 0:
        print(f"Saving {len_filtered_bookmarks} bookmarks in database")
    else:
        print("No new bookmarks to save in database")
        return

    records = [(bookmark._id, bookmark.created_at, bookmark.updated_at,
                bookmark.link, bookmark.title) for bookmark in filtered_bookmarks]

    try:
        connection = psycopg2.connect(
            user=config['db_username'], password=config['db_password'], host=config['db_host'], port=config['db_port'])
        cursor = connection.cursor()
        sql_insert_query = """INSERT INTO bookmark (_id, created_at, updated_at, link, title)
                            VALUES (%s,%s,%s,%s,%s)"""
        result = cursor.executemany(sql_insert_query, records)
        connection.commit()

    except (Exception, psycopg2.Error) as error:
        print("Failed inserting record into mobile table {}".format(error))
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_config():
    success = True

    token = os.getenv('RAINDROP_IO_TOKEN')
    if token is None:
        success = False
        print("Raindrop IO token is not provided")

    db_username = os.getenv('POSTGRES_USERNAME')
    if db_username is None:
        success = False
        print("DB username is not provided")

    db_password = os.getenv('POSTGRES_PASSWORD')
    if db_password is None:
        success = False
        print("DB password is not provided")

    db_host = os.getenv('POSTGRES_HOST')
    if db_host is None:
        success = False
        print("DB host is not provided")

    db_port = os.getenv('POSTGRES_PORT')
    if db_port is None:
        success = False
        print("DB port is not provided")

    if success:
        return {
            'token': token,
            'db_username': db_username,
            'db_password': db_password,
            'db_host': db_host,
            'db_port': db_port
        }
    else:
        sys.exit(1)


def get_bookmark_from_dict(item):
    return Bookmark(
        _id=item['_id'],
        created_at=item['created'],
        updated_at=item['lastUpdate'],
        link=item['link'], title=item['title'])


def get_bookmarks(config, most_recent_created_at_datetime):
    pages_to_skip = 0
    items = []

    headers = {
        'Authorization': f"Bearer {config['token']}"
    }

    while True:
        params = {
            'page': pages_to_skip,
            'perpage': MAX_BOOKMARKS_PER_PAGE,
            'sort': '-created'
        }

        response = requests.get(url=URL, params=params, headers=headers)

        if response.status_code == requests.codes.ok:
            data = response.json()
            items_data = data["items"]

            if len(items_data) > 0:
                items.extend(items_data)
                pages_to_skip += 1
                print(
                    f"Loaded page {pages_to_skip} with {len(items_data)} bookmarks")

                if most_recent_created_at_datetime is not None:
                    last_record_datetime = dateutil.parser.parse(
                        items_data[-1]['created']).replace(tzinfo=None)
                    if most_recent_created_at_datetime >= last_record_datetime:
                        return [
                            get_bookmark_from_dict(item)
                            for item in items], True
            else:
                return [
                    get_bookmark_from_dict(item)
                    for item in items], True
        else:
            print(f"Request failed with status code {response.status_code}")
            return [], False


def main():
    load_dotenv()
    config = get_config()
    save_pref = get_save_preference()
    most_recent_created_at_datetime = None

    if save_pref == SAVE_DB:
        most_recent_created_at_datetime = get_most_recent_created_at_for_bookmarks(
            config=config)

    bookmarks, success = get_bookmarks(config, most_recent_created_at_datetime)

    if success:
        if save_pref == SAVE_JSON:
            save_bookmarks_in_json_file(bookmarks)
        elif save_pref == SAVE_DB:
            save_bookmarks_in_db(config=config, bookmarks=bookmarks,
                                 most_recent_created_at_datetime=most_recent_created_at_datetime)


if __name__ == "__main__":
    main()
