import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO vehicle_rental
                    (
                        token_id, city, district, title, description, rent, deposit,
                        latitude, longitude, mobile, brand_and_model, rental_type,
                        rental_period, good_for, insurance_status, build_year,
                        daily_kilometer_limit, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads["token_id"],
                ads["city"],
                ads["district"],
                ads["title"],
                ads["description"],
                ads["rent"],
                ads["deposit"],
                ads["latitude"],
                ads["longitude"],
                ads["mobile"],
                ads["brand_and_model"],
                ads["rental_type"],
                ads["rental_period"],
                ads["good_for"],
                ads["insurance_status"],
                ads["build_year"],
                ads["daily_kilometer_limit"],
                ads["published_at"],
                ads["created_at"],
            ),
        )

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logging.error(f"Vehicle table error: {e}")
        return False

    finally:
        if cur:
            cur.close()
