def createTable(conn):

    cur = conn.cursor()

    # *****start create tables*****
    createScript = """
        CREATE TABLE IF NOT EXISTS vehicle_rental(
            id                      SERIAL PRIMARY KEY,
            token_id                varchar(30) DEFAULT NULL,
            city                    varchar(25) DEFAULT NULL,
            district                varchar(100) DEFAULT NULL,
            title                   varchar(500) DEFAULT NULL,
            description             text DEFAULT NULL,
            rent                    numeric DEFAULT NULL,
            deposit                 numeric DEFAULT NULL,
            latitude                numeric DEFAULT NULL,
            longitude               numeric DEFAULT NULL,
            mobile                  varchar(15) DEFAULT NULL,
            brand_and_model         varchar(100) DEFAULT NULL,
            rental_type             varchar(100) DEFAULT NULL,
            rental_period           varchar(255) DEFAULT NULL,
            good_for                varchar(255) DEFAULT NULL,
            insurance_status        varchar(150) DEFAULT NULL,
            build_year              int DEFAULT NULL,
            daily_kilometer_limit   int DEFAULT NULL,
            published_at            timestamp DEFAULT NULL,
            created_at              timestamp DEFAULT NULL,
            deleted_at              timestamp DEFAULT NULL
    )"""

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicle_rental_token_id
        ON vehicle_rental(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    # *****end create tables*****
