import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO tour_and_charter
                    (
                        token_id, city, district, title, description, price,
                        latitude, longitude, mobile, transport_type, tour_type,
                        tour_services, fixed_price, open_to_trade, hotel_rating,
                        departure_date, return_date, days_of_stay,
                        published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads.get("token_id"),
                ads.get("city"),
                ads.get("district"),
                ads.get("title"),
                ads.get("description"),
                ads.get("price"),
                ads.get("latitude"),
                ads.get("longitude"),
                ads.get("mobile"),
                ads.get("transport_type"),
                ads.get("tour_type"),
                ads.get("tour_services"),
                ads.get("fixed_price"),
                ads.get("open_to_trade"),
                ads.get("hotel_rating"),
                ads.get("departure_date"),
                ads.get("return_date"),
                ads.get("days_of_stay"),
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
