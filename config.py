import os
import sys
import argparse

BACKUP_LOCATION_DB = "db"
BACKUP_LOCATION_JSON = "json"

BACKUP_TYPE_FULL = "full"
BACKUP_TYPE_INCREMENTAL = "incremental"


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


def get_command_line_args():
    parser = argparse.ArgumentParser(
        description="This tool is used to backup bookmarks stored in Raindrop.io")

    parser.add_argument("-s",  "--save", help="Specify save location of backup",
                        choices=[BACKUP_LOCATION_DB, BACKUP_LOCATION_JSON], default=BACKUP_LOCATION_DB)
    parser.add_argument(
        "-f", "--file", help=f"Specify JSON file to save backup in, use in conjunction with `--save {BACKUP_LOCATION_JSON}``")
    parser.add_argument("-t", "--type", help="Specify type of backup", choices=[
                        BACKUP_TYPE_FULL, BACKUP_TYPE_INCREMENTAL], default=BACKUP_TYPE_INCREMENTAL)

    return parser.parse_args()
