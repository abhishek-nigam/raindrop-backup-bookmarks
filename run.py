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
from logger import logger
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


def save_as_json(bookmarks: List[Bookmark], file_path: str) -> None:
    '''
        Save bookmarks in JSON file
    '''

    data: List[Dict] = []
    
    save_location = os.path.join(
        "output", f"all_bookmarks_{int(time.time())}.json") # use file name with epoch seconds as default
    if file_path:
        save_location = os.path.normcase(file_path) # convert specified path to path as per OS

    for bookmark in bookmarks:
        data.append({
            "_id": bookmark._id,
            "created_at": bookmark.created_at,
            "updated_at": bookmark.updated_at,
            "link": bookmark.link,
            "title": bookmark.title,
            "tags": [tag._id for tag in bookmark.tags]
        })


    with open(save_location, "w") as out_file:
        json.dump({
            'bookmarks': data,
            "created_at": datetime.utcnow().isoformat()
        }, out_file)


def get_most_recent_bookmark_created_at_datetime(connection) -> Optional[datetime]:
    '''
        Get created_at of most recent created bookmark or 
        else return None if one is not available 
    '''

    logger.info("Fetching 'created_at' of most recent bookmark from database")

    with DatabaseConnection.Cursor(connection) as cursor:
        if cursor:
            try:
                sql_select_query = """SELECT created_at FROM bookmark ORDER BY created_at DESC LIMIT 1"""
                cursor.execute(sql_select_query)
                record = cursor.fetchone()
                if record:
                    return record[0].replace(tzinfo=None)
            except (Exception, psycopg2.Error) as error:
                logger.error("Failed selecting record from bookmark table {}".format(error))

    return None


def get_filtered_bookmarks(bookmarks: List[Bookmark], most_recent_created_at_datetime: datetime):
    '''
        Filter bookmarks to get only those whose created_at is greater
        than most recent created_at of bookmark from database
    '''
    return list(filter(lambda x: dateutil.parser.parse(
        x.created_at).replace(tzinfo=None) > most_recent_created_at_datetime, bookmarks))


def save_in_db(connection, bookmarks: List[Bookmark]) -> None:
    '''
        Save bookmarks, tags and bookmark tag mappings in database
    '''

    tag_records_set: Set[str] = set()
    bookmark_records:  List[Tuple[str, str, str, str, str]] = []
    bookmark_tag_mapping_records: List[Tuple[str, str]] = []

    len_bookmarks = len(bookmarks)
    if len_bookmarks > 0:
        logger.info(f"Saving {len_bookmarks} bookmarks in database")
    else:
        logger.info("No new bookmarks to save in database")
        return

    # convert models into tuple form to be used in sql execute statement
    for bookmark in bookmarks:
        bookmark_records.append((bookmark._id, bookmark.created_at, bookmark.updated_at,
                                 bookmark.link, bookmark.title))
        bookmark_tag_mapping_records.extend(
            [(mapping.bookmark_id, mapping.tag_id) for mapping in bookmark.mappings])
        tag_records_set.update([tag._id for tag in bookmark.tags]) # use a set to make a list of non-duplicate tags

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
            logger.error("Failed inserting records in bookmark table {}".format(error))

        try:
            sql_tag_insert_query = """
                            INSERT INTO tag (_id)
                            VALUES (%s)
                            ON CONFLICT (_id) DO NOTHING
                            """
            cursor.executemany(sql_tag_insert_query, tag_records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            logger.error("Failed inserting record in tag table {}".format(error))

        try:
            sql_tag_mapping_record_insert_query = """
                            INSERT INTO bookmark_tag_mapping (bookmark_id, tag_id)
                            VALUES (%s,%s)
                            ON CONFLICT (bookmark_id, tag_id) DO NOTHING
                            """
            cursor.executemany(sql_tag_mapping_record_insert_query, bookmark_tag_mapping_records)
            connection.commit()
        except (Exception, psycopg2.Error) as error:
            logger.error(
                "Failed inserting records in bookmark tag mapping table {}".format(error))


def get_bookmarks_from_api_response_items(items: List[Dict]) -> List[Bookmark]:
    '''
        Get bookmark model from API response dict
    '''
    bookmarks: List[Bookmark] = []

    for item in items:
        items_tags: List[Tag] = []
        bookmark_tag_mappings: List[BookmarkTagMapping] = []

        for item_tag_str in item['tags']:
            bookmark_tag_mappings.append(BookmarkTagMapping(item['_id'], item_tag_str))
            items_tags.append(Tag(item_tag_str))

        bookmarks.append(
            Bookmark(
                _id=item['_id'],
                created_at=item['created'],
                updated_at=item['lastUpdate'],
                link=item['link'],
                title=item['title'],
                tags=items_tags,
                mappings=bookmark_tag_mappings)
        )

    return bookmarks


def get_api_response_items(token: str, most_recent_bookmark_created_at_datetime: Optional[datetime]):
    '''
        Makes API call to Raindrop's server to get bookmarks
    '''

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

            if len(items_data) > 0: # if reponse is non-empty
                items.extend(items_data)
                pages_to_skip += 1
                logger.info(
                    f"Loaded page {pages_to_skip} with {len(items_data)} bookmarks")

                # is created_at of most recent bookamrk is available and 
                # created_at of last bookmark is less than most recent, then we don't
                # need to make any more API requests
                if most_recent_bookmark_created_at_datetime:
                    last_record_created_at_datetime = dateutil.parser.parse(
                        items_data[-1]['created']).replace(tzinfo=None)

                    if most_recent_bookmark_created_at_datetime >= last_record_created_at_datetime:
                        return items
            else: # is response is empty, this means that last page has been accessed
                return items
        else:
            logger.error(f"Request failed with status code {response.status_code}")
            return None


def wait_for_network_connection(max_tries: int) -> None:
    '''
        In case this script is run on boot, this function is used
        to wait until network has connection, or else exit after max_tries
    '''
    wait_for_seconds = 10
    no_of_tries = 1

    logger.info("Checking internet connection")

    while True:
        if no_of_tries > max_tries:
            logger.error(
                f"Couldn't get network connection after {max_tries} attempts, exiting")
            sys.exit(1)

        try:
            requests.head("http://www.google.com", timeout=5)
            return
        except (requests.ConnectionError, requests.Timeout) as e:
            pass

        logger.info(
            f"Waiting for internet connection. Next attempt in {wait_for_seconds} seconds")
        time.sleep(wait_for_seconds)
        wait_for_seconds = wait_for_seconds * 2
        no_of_tries = no_of_tries + 1


def main():
    # load configration
    load_dotenv()
    config = get_config()
    token = config['token']

    args = get_command_line_args()
    backup_location = args.save
    backup_type = args.type
    backup_file_name = args.file

    wait_for_network_connection(NETWORK_MAX_TRIES)

    if backup_location == BACKUP_LOCATION_DB:
        most_recent_bookmark_created_at_datetime = None

        with DatabaseConnection(config) as conn:
            if conn:
                if backup_type == BACKUP_TYPE_INCREMENTAL:
                    most_recent_bookmark_created_at_datetime = get_most_recent_bookmark_created_at_datetime(
                        conn)

                api_response_items = get_api_response_items(
                    token, most_recent_bookmark_created_at_datetime)
                if api_response_items:
                    bookmarks = get_bookmarks_from_api_response_items(
                        api_response_items) # parse API response into model objects

                    if most_recent_bookmark_created_at_datetime:
                        filtered_bookmarks = get_filtered_bookmarks(
                            bookmarks, most_recent_bookmark_created_at_datetime)
                        save_in_db(
                            conn, filtered_bookmarks)
                    else:
                        save_in_db(conn, bookmarks)

    elif backup_location == BACKUP_LOCATION_JSON:
        api_response_items = get_api_response_items(token, None)
        if api_response_items:
            bookmarks = get_bookmarks_from_api_response_items(
                api_response_items)
            save_as_json(bookmarks, backup_file_name)


if __name__ == "__main__":
    main()
