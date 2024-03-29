import os
import asyncio
from databend_driver import AsyncDatabendClient
import argparse
import datetime
from termcolor import colored


async def create_database(conn, database_name):
    """Creates a new database, dropping it first if it exists."""
    print(f"Creating database: {database_name}")
    await conn.exec(f"DROP DATABASE IF EXISTS {database_name}")
    await conn.exec(f"CREATE DATABASE {database_name}")


async def execute_sql_file(conn, file_path, database_name):
    """Executes SQL commands from a file in the specified database."""
    print(f"Executing SQL file: {file_path}")
    try:
        await conn.exec(f"USE {database_name}")
        with open(file_path, "r") as file:
            sql_script = file.read()
        commands = sql_script.split(";")
        for idx, command in enumerate(commands, start=1):
            command = command.strip()
            if command:
                print(f"Executing command #{idx}:\n{command}")
                await conn.exec(command)
        print("SQL file executed successfully.")
    except Exception as e:
        print(f"Error executing SQL file: {e}")
        raise


async def fetch_query_results(conn, query):
    """Fetches the results of a query."""
    rows = await conn.query_iter(query)
    return [row.values() async for row in rows]


def format_result_diff(result1, result2):
    """Formats the difference between two query results in a style similar to Git diff."""

    result1_set = set(map(tuple, result1))
    result2_set = set(map(tuple, result2))

    diff = []

    # Rows removed in result2
    for row in result1_set - result2_set:
        diff.append(colored(f"- {row}", "red"))

    # Rows added in result2
    for row in result2_set - result1_set:
        diff.append(colored(f"+ {row}", "green"))

    return "\n".join(diff)


async def execute_and_compare_queries(conn_v1, conn_v2, check_file, database_name):
    """Executes and compares queries from a file."""
    print(f"Executing and comparing queries from file: {check_file}")
    try:
        await conn_v1.exec(f"USE {database_name}")
        await conn_v2.exec(f"USE {database_name}")
        with open(check_file, "r") as file:
            queries = file.read().split(";")
        for idx, query in enumerate(queries, start=1):
            query = query.strip()
            if query:
                print(colored(f"Executing query #{idx}:", "green"))
                print(f"{query}")
                result_v1 = await fetch_query_results(conn_v1, query)
                result_v2 = await fetch_query_results(conn_v2, query)
                await compare_and_print_results(result_v1, result_v2, idx, query)
    except Exception as e:
        print(f"Error executing or comparing queries: {e}")
        raise


async def compare_and_print_results(result1, result2, query_idx, query_text):
    """Compares two query results and prints the difference."""
    if result1 != result2:
        print(f"Results differ at query #{query_idx}: {query_text}")
        diff = format_result_diff(result1, result2)
        print(diff)
        raise ValueError("Results are not consistent between V1 and V2.")
    else:
        print(colored(f"Query #{query_idx} results are the same.\n", "green"))


async def main():
    """Main function to execute and compare Databend queries."""
    parser = argparse.ArgumentParser(
        description="Run Databend queries and compare results."
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Setup the database by executing the setup SQL",
    )
    parser.add_argument("--database", type=str, help="Specify the database name to use")
    args = parser.parse_args()

    # Use the provided database name or create a default one
    if args.database:
        database_name = args.database
    else:
        today = datetime.datetime.now().strftime("%Y%m%d")
        database_name = f"double_check_{today}"

    dsn_v1 = os.getenv("DATABEND_DSN_V1", "default_dsn_v1")
    dsn_v2 = os.getenv("DATABEND_DSN_V2", "default_dsn_v2")

    setup_file = "sql/setup.sql"
    check_file = "sql/check.sql"

    print("Starting script execution.")

    try:
        client_v1 = AsyncDatabendClient(dsn_v1)
        conn_v1 = await client_v1.get_conn()

        if args.setup:
            await create_database(conn_v1, database_name)
            await execute_sql_file(conn_v1, setup_file, database_name)
        else:
            client_v2 = AsyncDatabendClient(dsn_v2)
            conn_v2 = await client_v2.get_conn()
            await execute_and_compare_queries(
                conn_v1, conn_v2, check_file, database_name
            )

    except Exception as e:
        print(f"Database connection or execution error: {e}")

    print("Script execution completed.")


asyncio.run(main())
