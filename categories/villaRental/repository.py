import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO villa_rental
                    (
                        token_id, city, rent, deposit, title, description, district,
                        latitude, longitude, mobile, area, land_area, year, rooms,
                        parking, warehouse, balcony, renovated, floor_material, wc,
                        cooler, heater, hot_water_supplier, direction, good_for,
                        pets_allowed, furnished, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads["token_id"],
                ads["city"],
                ads["rent"],
                ads["deposit"],
                ads["title"],
                ads["description"],
                ads["district"],
                ads["latitude"],
                ads["longitude"],
                ads["mobile"],
                ads["area"],
                ads["land_area"],
                ads["year"],
                ads["rooms"],
                ads["parking"],
                ads["warehouse"],
                ads["balcony"],
                ads["renovated"],
                ads["floor_material"],
                ads["wc"],
                ads["cooler"],
                ads["heater"],
                ads["hot_water_supplier"],
                ads["direction"],
                ads["good_for"],
                ads["pets_allowed"],
                ads["furnished"],
                ads["published_at"],
                ads["created_at"],
            ),
        )

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logging.error(f"Advertisement table error: {e}")
        return False

    finally:
        if cur:
            cur.close()
