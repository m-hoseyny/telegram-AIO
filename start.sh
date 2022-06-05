source aio/bin/activate;
pkill gunicorn;
python3 update.py && python3 -m bot;
