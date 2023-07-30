@ECHO OFF
python -m flask --app app.py --debug run -p 443 --cert adhoc
