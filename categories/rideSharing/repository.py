import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO ride_sharing
                    (
                        token_id, city, district, title, description, latitude, longitude, mobile, price, 
                        departure_location, destination, departure_date, number_of_companions, pets_allowed, 
                        includes_luggage_allowance, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads.get("token_id"),
                ads.get("city"),
                ads.get("district"),
                ads.get("title"),
                ads.get("description"),
                ads.get("latitude"),
                ads.get("longitude"),
                ads.get("mobile"),
                ads.get("price"),
                ads.get("departure_location"),
                ads.get("destination"),
                ads.get("departure_date"),
                ads.get("number_of_companions"),
                ads.get("pets_allowed"),
                ads.get("includes_luggage_allowance"),
                ads.get("published_at"),
                ads.get("created_at"),
            ),
        )

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logging.error(f"Ride sharing table error: {e}")
        return False

    finally:
        if cur:
            cur.close()
