#!/bin/bash
python manage.py migrate --noinput
gunicorn mon_projet.wsgi:application --bind 0.0.0.0:$PORT
