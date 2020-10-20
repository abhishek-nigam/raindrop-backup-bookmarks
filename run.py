import requests
import json
import time
import os
import sys
import psycopg2
import dateutil.parser
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
from models import Bookmark
from db import DatabaseConnection
from config import (
    get_config,
    get_command_line_args,
    BACKUP_LOCATION_DB,
    BACKUP_LOCATION_JSON,
    BACKUP_TYPE_INCREMENTAL
)

URL = "https://api.raindrop.io/rest/v1/raindrops/0"
MAX_BOOKMARKS_PER_PAGE = 50
NETWORK_MAX_TRIES = 6


def save_bookmarks_json(bookmarks: List[Bookmark], file_path: str) -> None:
    save_location = os.path.join(
        "output", f"all_bookmarks_{int(time.time())}.json")
    if file_path:
        save_location = os.path.normcase(file_path)

    with open(save_location, "w") as out_file:
        json.dump({
            'bookmarks': [vars(bookmark) for bookmark in bookmarks],
            "created_at": datetime.utcnow().isoformat()
        }, out_file)


def get_most_recent_bookmark_created_at_datetime(connection) -> Optional[datetime]:
    print("Fetching 'created_at' of most recent bookmark from database")

    with DatabaseConnection.Cursor(connection) as cursor:
        if cursor:
            try:
                sql_select_query = """SELECT created_at FROM bookmark ORDER BY created_at DESC LIMIT 1"""
                cursor.execute(sql_select_query)
                record = cursor.fetchone()
                if record:
                    return record[0].replace(tzinfo=None)
            except (Exception, psycopg2.Error) as error:
                print("Failed inserting record into mobile table {}".format(error))

    return None


def save_bookmarks_db(connection, bookmarks: List[Bookmark], most_recent_created_at_datetime: Optional[datetime]) -> None:

    filtered_bookmarks = bookmarks
    if most_recent_created_at_datetime:
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

    with DatabaseConnection.Cursor(connection) as cursor:
        try:
            sql_upsert_query = """
                            INSERT INTO bookmark (_id, created_at, updated_at, link, title)
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT (_id) DO UPDATE SET updated_at = EXCLUDED.updated_at, link = EXCLUDED.link, title = EXCLUDED.title
                            """
            cursor.executemany(sql_upsert_query, records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            print("Failed inserting record into mobile table {}".format(error))


def get_bookmark_from_dict(item: Dict) -> Bookmark:
    return Bookmark(
        _id=item['_id'],
        created_at=item['created'],
        updated_at=item['lastUpdate'],
        link=item['link'], title=item['title'])


def get_bookmarks(token: str, most_recent_bookmark_created_at_datetime: Optional[datetime]):
    pages_to_skip = 0
    items = []

    headers = {
        'Authorization': f"Bearer {token}"
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

                if most_recent_bookmark_created_at_datetime:
                    last_record_created_at_datetime = dateutil.parser.parse(
                        items_data[-1]['created']).replace(tzinfo=None)

                    if most_recent_bookmark_created_at_datetime >= last_record_created_at_datetime:
                        return [get_bookmark_from_dict(item)
                                for item in items]
            else:
                return [get_bookmark_from_dict(item)
                        for item in items]
        else:
            print(f"Request failed with status code {response.status_code}")
            return None

def wait_for_network_connection(max_tries: int) -> None:
    wait_for_seconds = 10
    no_of_tries = 1

    print("Checking internet connection")

    while True:
        if no_of_tries > max_tries:
            print(f"Couldn't get network connection after {max_tries} attempts, exiting")
            sys.exit(1)

        try:
            requests.head("http://www.google.com", timeout=5)
            return
        except (requests.ConnectionError, requests.Timeout) as e:
            pass

        print(f"Waiting for internet connection. Next attempt in {wait_for_seconds} seconds")
        time.sleep(wait_for_seconds)
        wait_for_seconds = wait_for_seconds * 2
        no_of_tries = no_of_tries + 1

def main():
    load_dotenv()
    config = get_config()
    token = config['token']

    args = get_command_line_args()

    wait_for_network_connection(NETWORK_MAX_TRIES)

    if args.save == BACKUP_LOCATION_DB:
        most_recent_bookmark_created_at_datetime = None

        with DatabaseConnection(config) as conn:
            if conn:
                if args.type == BACKUP_TYPE_INCREMENTAL:
                    most_recent_bookmark_created_at_datetime = get_most_recent_bookmark_created_at_datetime(
                        conn)

                bookmarks = get_bookmarks(
                    token, most_recent_bookmark_created_at_datetime)
                if bookmarks:
                    save_bookmarks_db(
                        conn, bookmarks, most_recent_bookmark_created_at_datetime)

    elif args.save == BACKUP_LOCATION_JSON:
        bookmarks = get_bookmarks(token, None)
        if bookmarks:
            save_bookmarks_json(bookmarks, args.file)


if __name__ == "__main__":
    main()
