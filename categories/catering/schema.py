def createTable(conn):
    cur = conn.cursor()

    createScript = """
        CREATE TABLE IF NOT EXISTS catering(
            id                      SERIAL PRIMARY KEY,
            token_id                varchar(30) DEFAULT NULL,
            city                    varchar(25) DEFAULT NULL,
            district                varchar(100) DEFAULT NULL,
            title                   varchar(500) DEFAULT NULL,
            description             text DEFAULT NULL,
            latitude                numeric DEFAULT NULL,
            longitude               numeric DEFAULT NULL,
            mobile                  varchar(15) DEFAULT NULL,
            specialties             varchar(1000) DEFAULT NULL,
            working_hours           varchar(150) DEFAULT NULL,
            minimum_order           varchar(100) DEFAULT NULL,
            guest_capacity          varchar(100) DEFAULT NULL,
            food_tasting            boolean DEFAULT NULL,
            published_at            timestamp DEFAULT NULL,
            created_at              timestamp DEFAULT NULL,
            deleted_at              timestamp DEFAULT NULL
        )
    """

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_catering_token_id
        ON catering(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    cur.close()
