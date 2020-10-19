import psycopg2


class DatabaseConnection:
    def __init__(self, config):
        self.config = config

    def __enter__(self):
        try:
            self.connection = psycopg2.connect(
                user=self.config['db_username'],
                password=self.config['db_password'],
                host=self.config['db_host'],
                port=self.config['db_port'])
            return self.connection
        except (Exception, psycopg2.Error) as error:
            print(f"Could not open connection to database {error}")
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()

    class Cursor():
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            try:
                self.cursor = self.connection.cursor()
                return self.cursor
            except (Exception, psycopg2.Error) as error:
                print(f"Could could not get cursor from database connection")
                return None

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.cursor:
                self.cursor.close()
