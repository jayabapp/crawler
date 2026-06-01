import pandas as pd
from datetime import datetime, timedelta


def lastDataLog(conn):
    print("Start getting last date of logs...")
    try:
        cur = conn.cursor()

        createLogTbl = """
            CREATE TABLE IF NOT EXISTS excel_logs(
                id              SERIAL PRIMARY KEY,
                tbl_name        VARCHAR(20) DEFAULT NULL,
                created_at      timestamp DEFAULT NULL
        )"""

        getLastLogs = """
            SELECT *
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY tbl_name ORDER BY created_at DESC) AS rn
                FROM excel_logs
            ) t
            WHERE rn = 1;
        """

        cur.execute(createLogTbl)
        conn.commit()
        cur.execute(getLastLogs)
        rows = cur.fetchall()

        lastLogs = {row[1]: row[2] for row in rows}

        return lastLogs

    except Exception as e:
        conn.rollback()
        print("Getting last date of logs failed. Error:", e)

    finally:
        cur.close()


def getDataFromDatabase(conn, lastDate, tblName, columns):
    print(f"Start get {tblName} data from database...")
    try:
        cur = conn.cursor()

        columnStr = ", ".join(columns)

        if lastDate is None:
            lastDate = datetime(1970, 1, 1)

        lastDate = lastDate - timedelta(hours=3, minutes=30)

        query = f"""
            SELECT {columnStr}
            FROM {tblName}
            WHERE deleted_at IS NULL
            AND created_at > %s
        """
        cur.execute(query, (lastDate,))
        data = cur.fetchall()

        return data

    except Exception as e:
        conn.rollback()
        print(f"Getting {tblName} data from database failed. Error:", e)
        return None

    finally:
        cur.close()


def exportDataToExcel(conn, tblName, columns, data):
    print(f"Start export {tblName} data...")
    try:
        if not data:
            print(f"No new data for {tblName}")
            return

        now = datetime.now()
        filenameTime = now.strftime("%Y%m%d_%H%M%S")

        df = pd.DataFrame(data, columns=columns)
        df.to_excel(f"dataService/excelData/{tblName}_{filenameTime}.xlsx", index=False)

        try:
            print(f"Start insert {tblName} log to database...")
            cur = conn.cursor()

            insertQuery = (
                """INSERT INTO excel_logs (tbl_name, created_at) VALUES (%s, %s)"""
            )
            cur.execute(insertQuery, (tblName, now))
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"Insert {tblName} log to database failed. Error:", e)
        finally:
            cur.close()

    except Exception as e:
        print(f"Export {tblName} data faile. Error:", e)
