import pytest
import pandas as pd
from unittest.mock import MagicMock

from mindsdb.integrations.handlers.mysql_handler.mysql_handler import MySQLHandler
from mindsdb.api.mysql.mysql_proxy.libs.constants.response_type import RESPONSE_TYPE

HANDLER_KWARGS = {
    "connection_data": {
        "host": "127.0.0.1",
        "port": "3306",
        "user": "root",
        "password": "supersecret",
        "database": "test",
        "ssl": False
    }
}

CERTS_ARCHIVE = "certs.tar"
CERTS_DIR = "mysql"

expected_columns = ["col_one", "col_two", "col_three", "col_four"]

table_for_creation = "test_mdb"

@pytest.fixture(scope="class")
def database_connection_and_cursor():
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


# def get_certs():
#     certs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysql")
#     certs = {}
#     for cert_key, fname in [("ssl_ca", "ca.pem"), ("ssl_cert", "client-cert.pem"), ("ssl_key", "client-key.pem")]:
#         cert_file = os.path.join(certs_dir, fname)
#         certs[cert_key] = cert_file
#     return certs


# def get_certificates(container):
#     cur_dir = os.path.dirname(os.path.abspath(__file__))
#     archive_path = os.path.join(cur_dir, CERTS_ARCHIVE)
#     with open(archive_path, "wb") as f:
#         bits, _ = container.get_archive('/var/lib/mysql')
#         for chunk in bits:
#             f.write(chunk)

#     with tarfile.open(archive_path) as tf:
#         tf.extractall(path=cur_dir)
#     certs = get_certs()
#     HANDLER_KWARGS["connection_data"].update(certs)


# def waitReadiness(container, timeout=30):
#     threshold = time.time() + timeout
#     ready_msg = "/usr/sbin/mysqld: ready for connections. Version: '8.0.27'"
#     while True:
#         lines = container.logs().decode()
#         # container fully ready
#         # because it reloads the db server during initialization
#         # need to check that the 'ready for connections' has found second time
#         if lines.count(ready_msg) >= 2:
#             break
#         if time.time() > threshold:
#             raise Exception("timeout exceeded, container is still not ready")


@pytest.fixture(scope="module", params=[{"ssl": False}], ids=["NoSSL"])
def handler(request):
    # with_ssl = request.param["ssl"]
    # if with_ssl:
    #     get_certificates(container)
    handler = MySQLHandler('test_mysql_handler', **HANDLER_KWARGS)
    yield handler

def check_valid_response(res):
    if res.resp_type == RESPONSE_TYPE.TABLE:
        assert res.data_frame is not None, "expected to have some data, but got None"
    assert res.error_code == 0, f"expected to have zero error_code, but got {res.error_code}"
    assert res.error_message is None, f"expected to have None in error message, but got {res.error_message}"

def get_table_names(handler):
    res = handler.get_tables()
    tables = res.data_frame
    assert tables is not None, "expected to have some tables in the db, but got None"
    assert 'table_name' in tables, f"expected to get 'table_name' column in the response:\n{tables}"
    return list(tables['table_name'])

class TestMySQLHandler:
    def test_connect(self, handler):
        handler.connect()
        assert handler.is_connected, "connection error"

    def test_check_connection(self, handler):
        res = handler.check_connection()
        assert res.success, res.error_message


@pytest.mark.usefixtures("handler", "database_connection_and_cursor")
class TestMySQLHandlerQuery:
    def test_native_query_show_dbs(self, handler):
        dbs = handler.native_query("SHOW DATABASES;")
        dbs = dbs.data_frame
        assert dbs is not None, "expected to get some data, but got None"
        assert 'Database' in dbs, f"expected to get 'Database' column in response:\n{dbs}"
        dbs = list(dbs["Database"])
        expected_db = HANDLER_KWARGS["connection_data"]["database"]
        assert expected_db in dbs, f"expected to have {expected_db} db in response: {dbs}"

    def test_select_query(self, handler):
        limit = 3
        query = "SELECT * FROM test;"
        res = handler.query(query)
        check_valid_response(res)
        got_rows = res.data_frame.shape[0]
        want_rows = limit
        assert (
            got_rows == want_rows
        ), f"expected to have {want_rows} rows in response but got: {got_rows}"


class TestMySQLHandlerTables:
    def test_get_tables(self, handler):
        res = handler.get_tables()
        tables = res.data_frame
        test_table = get_table_names(handler)
        assert (
            tables is not None
        ), "expected to have some table_name in the db, but got None"
        assert (
            "table_name" in tables
        ), f"expected to get 'table_name' column in the response:\n{tables}"
        # get a specific table from the tables list
        assert "test" in test_table, f"expected to have 'test' table in the db but got: {test_table}"


    def test_create_table(self, handler):
        new_table = table_for_creation
        res = handler.native_query(f"CREATE TABLE IF NOT EXISTS {new_table} (test_col INT)")
        check_valid_response(res)
        tables = get_table_names(handler)
        assert new_table in tables, f"expected to have {new_table} in database, but got: {tables}"

#TODO - edit this test so that it can be run on it's own - perhaps run drop table as a clean up method? 

    def test_drop_table(self, handler):
        drop_table = table_for_creation
        res = handler.native_query(f"DROP TABLE IF EXISTS {drop_table}")
        check_valid_response(res)
        tables = get_table_names(handler)
        assert drop_table not in tables


class TestMySQLHandlerColumns:
    def test_get_columns(self, handler):
        described = handler.get_columns("test")
        describe_data = described.data_frame
        check_valid_response(described)
        got_columns = list(describe_data.iloc[:, 0])
        assert got_columns == expected_columns, f"expected to have next columns in test table:\n{expected_columns}\nbut got:\n{got_columns}"


class TestMySQLHandlerDisconnect:
    def test_disconnect(self, handler):
        handler.disconnect()
        assert handler.is_connected == False, "failed to disconnect"

    def test_check_connection(self, handler):
        res = handler.check_connection()
        assert res.success, res.error_message
