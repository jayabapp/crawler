def createTable(conn):

    cur = conn.cursor()

    # *****start create tables*****
    createScript = """
        CREATE TABLE IF NOT EXISTS villa_rental(
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
            area                    int DEFAULT NULL,
            land_area                int DEFAULT NULL,
            year                    int DEFAULT NULL,
            rooms                   int DEFAULT NULL,
            parking                 boolean DEFAULT NULL,
            warehouse               boolean DEFAULT NULL,
            balcony                 boolean DEFAULT NULL,
            renovated               boolean DEFAULT NULL,
            floor_material          varchar(50) DEFAULT NULL,
            wc                      varchar(50) DEFAULT NULL,
            cooler                  varchar(50) DEFAULT NULL,
            heater                  varchar(50) DEFAULT NULL,
            hot_water_supplier      varchar(50) DEFAULT NULL,
            direction               varchar(20) DEFAULT NULL,
            good_for                varchar(100) DEFAULT NULL,
            pets_allowed            varchar(50) DEFAULT NULL,
            furnished               boolean DEFAULT NULL,
            published_at            timestamp DEFAULT NULL,
            created_at              timestamp DEFAULT NULL,
            deleted_at              timestamp DEFAULT NULL
    )"""

    createIndexScript = """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_villa_rental_token_id
        ON villa_rental(token_id);
    """

    cur.execute(createScript)
    cur.execute(createIndexScript)

    conn.commit()
    # *****end create tables*****
