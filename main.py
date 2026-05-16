import logging
import random
import sys
import threading
import time
import traceback
from importlib import import_module

from dotenv import load_dotenv

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s",
)


def getAttr(module, *names, default=None):
    for name in names:
        if hasattr(module, name):
            return getattr(module, name)

    return default


def connectDatabaseSafe():
    databaseModule = import_module("core.database")

    connectDatabase = getAttr(
        databaseModule,
        "connectDatabase",
        "connect_database",
    )

    if not connectDatabase:
        raise AttributeError(
            "داخل core/database.py باید تابع connectDatabase یا connect_database داشته باشی."
        )

    return connectDatabase()


def runSchemaIfExists(conn, categoryName):
    try:
        schemaModule = import_module(f"categories.{categoryName}.schema")

        createTable = getAttr(
            schemaModule,
            "createTable",
            "createTables",
            "create_table",
            "create_tables",
        )

        if createTable:
            createTable(conn)

    except ModuleNotFoundError:
        logging.warning(f"No schema module found for {categoryName}. Skipping schema.")
    except Exception as e:
        logging.error(f"Schema execution failed for {categoryName}: {e}")
        logging.error(traceback.format_exc())


def loadCategoryModules(categoryName):
    return {
        "config": import_module(f"categories.{categoryName}.config"),
        "extractor": import_module(f"categories.{categoryName}.extractor"),
        "filters": import_module(f"categories.{categoryName}.filters"),
        "repository": import_module(f"categories.{categoryName}.repository"),
    }


def runCategory(categoryName):
    from core.tokenFetcher import fetchTokens

    while True:
        conn = None

        try:
            logging.info(f"Starting {categoryName} crawler...")

            categoryModules = loadCategoryModules(categoryName)

            conn = connectDatabaseSafe()

            runSchemaIfExists(conn, categoryName)

            fetchTokens(
                conn=conn,
                categoryName=categoryName,
                categoryConfig=categoryModules["config"],
                extractorModule=categoryModules["extractor"],
                filtersModule=categoryModules["filters"],
                repositoryModule=categoryModules["repository"],
            )

        except Exception as e:
            logging.error(f"{categoryName} crawler crashed: {e}")
            logging.error(traceback.format_exc())

            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

            sleepTime = random.uniform(120, 300)
            logging.info(
                f"Restarting {categoryName} crawler after {int(sleepTime)} seconds..."
            )
            time.sleep(sleepTime)


def startAllCategories():
    categories = [
        "villaRental",
        "vehicleRental",
        "tourAndCharter",
        "rentTemporary",
        "rideSharing",
    ]

    threads = []

    for categoryName in categories:
        thread = threading.Thread(
            target=runCategory,
            args=(categoryName,),
            name=categoryName,
            daemon=False,
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


def main():
    if len(sys.argv) == 1:
        startAllCategories()
        return

    categoryName = sys.argv[1].strip()

    if categoryName == "all":
        startAllCategories()
        return

    allowedCategories = {
        "villaRental",
        "vehicleRental",
        "tourAndCharter",
        "rentTemporary",
        "rideSharing",
    }

    if categoryName not in allowedCategories:
        print("Invalid category.")
        print("Use one of these:")
        print("python main.py")
        print("python main.py all")
        print("python main.py villaRental")
        print("python main.py vehicleRental")
        print("python main.py tourAndCharter")
        print("python main.py rentTemporary")
        print("python main.py rideSharing")
        return

    runCategory(categoryName)


if __name__ == "__main__":
    main()
