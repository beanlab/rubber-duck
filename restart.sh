kill `ps -ae | grep python | cut -d ' ' -f 3`
nohup poetry run python discord_bot2.py --restarted >> /tmp/duck.log &