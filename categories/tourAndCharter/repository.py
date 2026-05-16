import logging


def insertAd(conn, ads):
    cur = None

    try:
        cur = conn.cursor()

        cur.execute(
            """
                INSERT INTO tour_and_charter
                    (
                        token_id, city, district, title, description, price, latitude, longitude, mobile, transport_type, 
                        tour_type, tour_services, fixed_price, open_to_trade, hotel_rating, departure_date, return_date, 
                        days_of_stay, published_at, created_at
                    )
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (token_id) DO NOTHING
            """,
            (
                ads["token_id"],
                ads["city"],
                ads["district"],
                ads["title"],
                ads["description"],
                ads["price"],
                ads["latitude"],
                ads["longitude"],
                ads["mobile"],
                ads["transport_type"],
                ads["tour_type"],
                ads["tour_services"],
                ads["fixed_price"],
                ads["open_to_trade"],
                ads["hotel_rating"],
                ads["hotel_name"],
                ads["departure_date"],
                ads["return_date"],
                ads["days_of_stay"],
                ads["published_at"],
                ads["created_at"],
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
