def createTable(conn):
    cur = conn.cursor()

    createScript = """
        CREATE TABLE IF NOT EXISTS rent_temporary(
            id                      SERIAL PRIMARY KEY,
            token_id                varchar(30) DEFAULT NULL,
            category                varchar(30) DEFAULT NULL,
            city                    varchar(25) DEFAULT NULL,
            district                varchar(100) DEFAULT NULL,
            title                   varchar(500) DEFAULT NULL,
            description             text DEFAULT NULL,
            latitude                numeric DEFAULT NULL,
            longitude               numeric DEFAULT NULL,
            mobile                  varchar(15) DEFAULT NULL,
            area                    int DEFAULT NULL,
            rooms                   int DEFAULT NULL,
            standard_capacity       varchar(20) DEFAULT NULL,
            extra_capacity          varchar(20) DEFAULT NULL,
            weekday_rate            numeric DEFAULT NULL,
            weekend_rate            numeric DEFAULT NULL,
            special_dates_rate      numeric DEFAULT NULL,
            extra_person_charge     numeric DEFAULT NULL,
            features                jsonb DEFAULT NULL,                        
            published_at            timestamp DEFAULT NULL,
            created_at              timestamp DEFAULT NULL,
            deleted_at              timestamp DEFAULT NULL
        )
    """

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rent_temporary_token_id
        ON rent_temporary(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    cur.close()
