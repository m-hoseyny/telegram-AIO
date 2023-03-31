source aio/bin/activate;
pkill gunicorn;
python3.9 update.py && python3.9 -m bot;
