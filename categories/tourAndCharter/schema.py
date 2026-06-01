def createTable(conn):
    cur = conn.cursor()

    createScript = """
        CREATE TABLE IF NOT EXISTS tour_and_charter(
            id                      SERIAL PRIMARY KEY,
            token_id                varchar(30) DEFAULT NULL,
            city                    varchar(25) DEFAULT NULL,
            district                varchar(100) DEFAULT NULL,
            title                   varchar(500) DEFAULT NULL,
            description             text DEFAULT NULL,
            price                   numeric DEFAULT NULL,
            latitude                numeric DEFAULT NULL,
            longitude               numeric DEFAULT NULL,
            mobile                  varchar(15) DEFAULT NULL,
            transport_type          varchar(20) DEFAULT NULL,
            tour_type               varchar(255) DEFAULT NULL,
            tour_services           varchar(500) DEFAULT NULL,
            fixed_price             boolean DEFAULT NULL,
            open_to_trade           boolean DEFAULT NULL,
            hotel_rating            varchar(20) DEFAULT NULL,
            departure_date          varchar(100) DEFAULT NULL,
            return_date             varchar(100) DEFAULT NULL,
            days_of_stay            varchar(50) DEFAULT NULL,
            published_at            timestamp DEFAULT NULL,
            created_at              timestamp DEFAULT NULL,
            deleted_at              timestamp DEFAULT NULL
        )
    """

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tour_and_charter_token_id
        ON tour_and_charter(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    cur.close()
