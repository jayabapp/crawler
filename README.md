# Div-Crawlers
All div crawlers together



# How to export data to Excel
    python3 -m dataService.dataMain



# How to run with docker
    <!-- Start if you never login before or you ran into a CAPTCHA do this if not skip this -->
        <!-- For all phones. 1 is just an example -->
        1. mkdir -p profiles/phone1
        2. DIVAR_PROFILE_DIR=$(pwd)/profiles/phone1 python3 -m core.login (docker compose run login_phone1)
        3. Login into website with your phone number
        4. Try to see phone number of an ad
        5. If you can see the phone number close the webpage then press ENTER in termina
    <!-- End if you never login before or you ran into a CAPTCHA do this if not skip this -->
    
    docker compose up -d --build (docker compose up -d rent_worker_1 rent_worker_2)



# How to use:
    <!-- Start if you never login before or you ran into a CAPTCHA do this if not skip this -->
    1. Run login.py
    2. Try to see phone number of an ad
    3. If you can see the phone number close the webpage then press ENTER in termina
    <!-- End if you never login before or you ran into a CAPTCHA do this if not skip this -->
    
    Run main.py

    <!-- If you want to run specific crawler try this -->
    python3 main.py CRAWLER_NAME


# Env file:
    USERNAME_DB="database username"
    PASSWORD_DB="database password"
    HOSTNAME_DB="database host"
    DATABASE_DB="database name"


    TELEGRAM_BOT_TOKEN="telegram bot token"
    TELEGRAM_CHAT_ID="your user ID (int)"

    CONTACT_REQUEST_MIN_DELAY=45
    CONTACT_REQUEST_MAX_EXTRA_DELAY=35
    CONTACT_CAPTCHA_COOLDOWN_SECONDS=3600
    CONTACTS_BEFORE_LONG_COOLDOWN=12
    CONTACT_LONG_COOLDOWN_MIN=300
    CONTACT_LONG_COOLDOWN_MAX=500


# If you change:
    sudo docker compose down
    sudo docker compose build --no-cache
    sudo docker compose up