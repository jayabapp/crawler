import logging
from psycopg2.extras import Json


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO rent_temporary
                    (
                        token_id, category, city, district, title, description, latitude, longitude, mobile, area, rooms, 
                        standard_capacity, extra_capacity, weekday_rate, weekend_rate, special_dates_rate, 
                        extra_person_charge, features, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads["token_id"],
                ads["category"],
                ads["city"],
                ads["district"],
                ads["title"],
                ads["description"],
                ads["latitude"],
                ads["longitude"],
                ads["mobile"],
                ads["area"],
                ads["rooms"],
                ads["standard_capacity"],
                ads["extra_capacity"],
                ads["weekday_rate"],
                ads["weekend_rate"],
                ads["special_dates_rate"],
                ads["extra_person_charge"],
                Json(ads["features"]),
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
