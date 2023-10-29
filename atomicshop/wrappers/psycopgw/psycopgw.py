import psycopg2

from ...print_api import print_api


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
            port: str = '5432'
    ):
        self.dbname: str = dbname
        self.user: str = user
        self.password: str = password
        self.host: str = host
        self.port: str = port

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
            self.cursor = self.connection.cursor()
            print_api("Successfully connected to the database.")
        except (Exception, psycopg2.Error) as error:
            print_api(f"Error while connecting to PostgreSQL: {error}", error_type=True)

    def execute_query(self, query):
        """
        Execute SQL query.
        :param query:
        :return:
        """

        if self.cursor:
            try:
                self.cursor.execute(query)
                return self.cursor.fetchall()
            except (Exception, psycopg2.Error) as error:
                print_api(f"Error executing the query: {error}", error_type=True)
        else:
            print_api("Connection not established. Call connect() method first.", error_type=True)

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
        port: str = '5432'
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
    :return:
    """

    postgresql_connection = PostgreSQLConnection(dbname, user, password, host, port)
    postgresql_connection.connect()
    data = postgresql_connection.execute_query(query)
    postgresql_connection.close()

    return data
