python manage.py migrate --noinput
if [ "$DJANGO_SUPERUSER_USERNAME"]; then 
    python manage.py create superuser \
        --noinput \
        --username $DJANGO_SUPERUSER_USERNAME \
        --email $DJANGO_SUPERUSER_EMAIL
fi

web: gunicorn mon_projet.wsgi:application --bind 0.0.0.0:$PORT
