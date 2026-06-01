import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO catering
                    (
                        token_id, city, district, title, description, latitude, longitude, mobile, specialties, 
                        working_hours, minimum_order, guest_capacity, food_tasting, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ads.get("specialties"),
                ads.get("working_hours"),
                ads.get("minimum_order"),
                ads.get("guest_capacity"),
                ads.get("food_tasting"),
                ads.get("published_at"),
                ads.get("created_at"),
            ),
        )

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logging.error(f"Tour and charter table error: {e}")
        return False

    finally:
        if cur:
            cur.close()
