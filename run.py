import requests
import json
import time
import os
import sys
import psycopg2
import dateutil.parser
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv
from models import Bookmark, BookmarkTagMapping, Tag
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


def save_as_json(bookmarks: List[Bookmark], tags: List[Tag], bookmark_tag_mappings: List[BookmarkTagMapping], file_path: str) -> None:
    save_location = os.path.join(
        "output", f"all_bookmarks_{int(time.time())}.json")
    if file_path:
        save_location = os.path.normcase(file_path)

    with open(save_location, "w") as out_file:
        json.dump({
            'bookmarks': [vars(bookmark) for bookmark in bookmarks],
            'tags': [tag._id for tag in tags],
            'bookmark_tag_mappings': [(mapping.bookmark_id, mapping.tag_id) for mapping in bookmark_tag_mappings],
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


def get_filtered_bookmarks(bookmarks: List[Bookmark], most_recent_created_at_datetime: datetime):
    return list(filter(lambda x: dateutil.parser.parse(
        x.created_at).replace(tzinfo=None) > most_recent_created_at_datetime, bookmarks))


def save_in_db(connection, bookmarks: List[Bookmark]) -> None:
    tag_records_set: Set[str] = set()
    bookmark_records:  List[Tuple[str, str, str, str, str]] = []
    bookmark_tag_mapping_records: List[Tuple[str, str]] = []

    len_bookmarks = len(bookmarks)
    if len_bookmarks > 0:
        print(f"Saving {len_bookmarks} bookmarks in database")
    else:
        print("No new bookmarks to save in database")
        return

    for bookmark in bookmarks:
        bookmark_records.append((bookmark._id, bookmark.created_at, bookmark.updated_at,
                                 bookmark.link, bookmark.title))
        bookmark_tag_mapping_records.extend(
            [(mapping.bookmark_id, mapping.tag_id) for mapping in bookmark.mappings])
        tag_records_set.update([tag._id for tag in bookmark.tags])

    tag_records = [(tag,) for tag in tag_records_set]

    with DatabaseConnection.Cursor(connection) as cursor:
        try:
            sql_bookmark_upsert_query = """
                            INSERT INTO bookmark (_id, created_at, updated_at, link, title)
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT (_id) DO UPDATE SET updated_at = EXCLUDED.updated_at, link = EXCLUDED.link, title = EXCLUDED.title
                            """
            cursor.executemany(sql_bookmark_upsert_query, bookmark_records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            print("Failed inserting records in bookmark table {}".format(error))

        try:
            sql_tag_insert_query = """
                            INSERT INTO tag (_id)
                            VALUES (%s)
                            ON CONFLICT (_id) DO NOTHING
                            """
            cursor.executemany(sql_tag_insert_query, tag_records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            print("Failed inserting record in tag table {}".format(error))

        try:
            sql_tag_mapping_record_insert_query = """
                            INSERT INTO bookmark_tag_mapping (bookmark_id, tag_id)
                            VALUES (%s,%s)
                            ON CONFLICT (bookmark_id, tag_id) DO NOTHING
                            """
            cursor.executemany(sql_tag_mapping_record_insert_query, bookmark_tag_mapping_records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            print(
                "Failed inserting records in bookmark tag mapping table {}".format(error))


def get_bookmark_from_dict(item: Dict) -> Bookmark:
    return Bookmark(
        _id=item['_id'],
        created_at=item['created'],
        updated_at=item['lastUpdate'],
        link=item['link'], title=item['title'])


def get_models_from_api_response_items(items: List[Dict]) -> Tuple[List[Bookmark], List[Tag], List[BookmarkTagMapping]]:
    bookmarks: List[Bookmark] = []
    tags_set: Set[str] = set()
    bookmark_tag_mappings: List[BookmarkTagMapping] = []

    for item in items:
        items_tags: List[Tag] = []
        mappings: List[BookmarkTagMapping] = []

        for item_tag_str in item['tags']:
            bookmark_tag_mappings.append(
                BookmarkTagMapping(item['_id'], item_tag_str)
            )
            mappings.append(BookmarkTagMapping(item['_id'], item_tag_str))
            items_tags.append(Tag(item_tag_str))

        bookmarks.append(
            Bookmark(
                _id=item['_id'],
                created_at=item['created'],
                updated_at=item['lastUpdate'],
                link=item['link'],
                title=item['title'],
                tags=items_tags,
                mappings=mappings)
        )

        tags_set.update(item['tags'])

    return bookmarks, [Tag(tag) for tag in tags_set], bookmark_tag_mappings


def get_api_response_items(token: str, most_recent_bookmark_created_at_datetime: Optional[datetime]):
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
                        return items
            else:
                return items
        else:
            print(f"Request failed with status code {response.status_code}")
            return None


def wait_for_network_connection(max_tries: int) -> None:
    wait_for_seconds = 10
    no_of_tries = 1

    print("Checking internet connection")

    while True:
        if no_of_tries > max_tries:
            print(
                f"Couldn't get network connection after {max_tries} attempts, exiting")
            sys.exit(1)

        try:
            requests.head("http://www.google.com", timeout=5)
            return
        except (requests.ConnectionError, requests.Timeout) as e:
            pass

        print(
            f"Waiting for internet connection. Next attempt in {wait_for_seconds} seconds")
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

                api_response_items = get_api_response_items(
                    token, most_recent_bookmark_created_at_datetime)
                if api_response_items:
                    bookmarks, _, _ = get_models_from_api_response_items(
                        api_response_items)

                    if most_recent_bookmark_created_at_datetime:
                        filtered_bookmarks = get_filtered_bookmarks(
                            bookmarks, most_recent_bookmark_created_at_datetime)
                        save_in_db(
                            conn, filtered_bookmarks)
                    else:
                        save_in_db(conn, bookmarks)

    elif args.save == BACKUP_LOCATION_JSON:
        api_response_items = get_api_response_items(token, None)
        if api_response_items:
            bookmarks, tags, bookmark_tag_mappings = get_models_from_api_response_items(
                api_response_items)
            save_as_json(bookmarks, tags, bookmark_tag_mappings, args.file)


if __name__ == "__main__":
    main()
