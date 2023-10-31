import psycopg2
import atexit

from ...print_api import print_api


# If we check 'get_query_data' with 'no_disconnect' set to True, we can import it from this file.
DB_CONNECTION = None


@atexit.register
def close_db_connection():
    """
    Close the database connection.
    :return:
    """
    global DB_CONNECTION

    if DB_CONNECTION is not None:
        DB_CONNECTION.close()
        DB_CONNECTION = None


class PostgreSQLConnection:
    """
    PostgreSQLConnection class is a wrapper for psycopg2 library.
    """

    def __init__(
            self,
            dbname: str,
            user: str,
            password: str,
            host: str = 'localhost',
            port: str = '5432',
            named_cursor: bool = False
    ):
        """
        Initiate PostgreSQLConnection class.
        :param dbname:
        :param user:
        :param password:
        :param host:
        :param port:
        :param named_cursor: bool, use named cursor, this is needed to get the data in chunks to use less memory
            on the server. The chunks are specified in the 'execute_query' method.
            Sometimes if 'named_cursor' is 'True', the 'execute_query' method returns None for the 'column_names'
            and you will get only the result list without the column names.
        """

        self.dbname: str = dbname
        self.user: str = user
        self.password: str = password
        self.host: str = host
        self.port: str = port

        self.named_cursor: bool = named_cursor

        self.connection = None
        self.cursor = None

    def connect(self):
        """
        Connect to PostgreSQL database.
        :return:
        """
        try:
            self.connection = psycopg2.connect(
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )

            if not self.named_cursor:
                self.cursor = self.connection.cursor()
            else:
                # Use a named cursor
                self.cursor = self.connection.cursor(name='named_cursor')

            print_api("Successfully connected to the database.")
        except (Exception, psycopg2.Error) as error:
            print_api(f"Error while connecting to PostgreSQL: {error}", error_type=True)

    def is_connected(self):
        """
        Check if the connection is established.
        :return: bool, True if the connection is established, False otherwise.
        """

        if self.connection and self.connection.closed == 0:
            return True

        return False

    def test_connection(self):
        """
        Test the connection.
        :return: bool, True if the connection is established, False otherwise.
        """

        if not self.is_connected():
            return False

        try:
            self.cursor.execute("SELECT 1;")
            # self.cursor.execute("SELECT version();")
            # self.cursor.fetchall()
            return True
        except (Exception, psycopg2.Error) as error:
            print_api(f"Error while testing the connection to PostgreSQL: {error}", error_type=True)
            return False

    def execute_query(self, query, batch_size=100):
        """
        Execute SQL query.
        :param query: string, SQL query.
        :param batch_size: int, batch size. Only used when 'named_cursor' during 'init' is True. Since the named cursor
            is used, the query is executed in batches. The batch size is the number of rows that will be fetched
            at a time. This is needed to not overload the memory.
        :return:
        """

        if self.cursor:
            try:
                self.cursor.execute(query)

                if self.cursor.description:
                    # Get column names.
                    column_names = [desc[0] for desc in self.cursor.description]
                else:
                    column_names = None
                # column_names = self.get_column_names(table_name)

                if not self.named_cursor:
                    # Fetch data.
                    data = self.cursor.fetchall()
                else:
                    # Fetch data in batches.
                    data = []
                    while True:
                        rows = self.cursor.fetchmany(batch_size)
                        if not rows:
                            break
                        data.extend(rows)

                # Sometimes 'named_cursor' returns None for the 'column_names'.
                if column_names:
                    # Convert data to list of dictionaries.
                    result = [dict(zip(column_names, row)) for row in data]
                else:
                    result = data

                return result
            except (Exception, psycopg2.Error) as error:
                print_api(f"Error executing the query: {error}", error_type=True)
        else:
            print_api("Connection not established. Call connect() method first.", error_type=True)

    def get_column_names(self, table_name):
        query = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        """
        self.cursor.execute(query)
        columns = [row[0] for row in self.cursor.fetchall()]
        return columns

    def close(self):
        if self.connection:
            self.cursor.close()
            self.connection.close()
            print_api("PostgreSQL connection is closed.")


def get_query_data(
        query: str,
        dbname: str,
        user: str,
        password: str,
        host: str = 'localhost',
        port: str = '5432',
        named_cursor: bool = False,
        leave_connected: bool = False
):
    """
    Get data from PostgreSQL database. During initiation, the class will connect to the database.
        Get the query and close the database connection.
    :param query: string, SQL query.
    :param dbname: string, database name.
    :param user: string, username.
    :param password: string, password.
    :param host: string, host IP address.
    :param port: string, port number.
    :param named_cursor: bool, use named cursor, Check the 'PostgreSQLConnection' class for more information.
    :param leave_connected: bool, leave the connection open.
    :return:
    """

    global DB_CONNECTION

    if DB_CONNECTION is None:
        DB_CONNECTION = PostgreSQLConnection(dbname, user, password, host, port, named_cursor)

    if not DB_CONNECTION.is_connected():
        DB_CONNECTION.connect()

    data = None
    try:
        data = DB_CONNECTION.execute_query(query)
    except (Exception, psycopg2.Error):
        leave_connected = False

    if not leave_connected:
        DB_CONNECTION.close()
        DB_CONNECTION = None

    return data
