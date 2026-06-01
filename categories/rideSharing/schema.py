def createTable(conn):
    cur = conn.cursor()

    createScript = """
        CREATE TABLE IF NOT EXISTS ride_sharing(
            id                              SERIAL PRIMARY KEY,
            token_id                        varchar(30) DEFAULT NULL,
            city                            varchar(25) DEFAULT NULL,
            district                        varchar(100) DEFAULT NULL,
            title                           varchar(500) DEFAULT NULL,
            description                     text DEFAULT NULL,
            latitude                        numeric DEFAULT NULL,
            longitude                       numeric DEFAULT NULL,
            mobile                          varchar(15) DEFAULT NULL,
            price                           numeric DEFAULT NULL,
            departure_location              varchar(30) DEFAULT NULL,
            destination                     varchar(30) DEFAULT NULL,
            departure_date                  varchar(20) DEFAULT NULL,
            number_of_companions            varchar(10) DEFAULT NULL,
            pets_allowed                    boolean DEFAULT NULL,
            includes_luggage_allowance      boolean DEFAULT NULL,
            published_at                    timestamp DEFAULT NULL,
            created_at                      timestamp DEFAULT NULL,
            deleted_at                      timestamp DEFAULT NULL
        )
    """

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ride_sharing_token_id
        ON ride_sharing(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    cur.close()
