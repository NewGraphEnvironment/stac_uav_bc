#!/bin/bash

# this was before and works to bang right into rstudio.a11s.one
source /home/airvine/stac-env/bin/activate
nohup stac-fastapi-pgstac --host 0.0.0.0 --port 8000 2>&1 | tee -a stac.log & while :; do sleep 3600; truncate -s 10M stac.log; done &
sleep 5
# source /home/airvine/stac-env/bin/activate
# cd /home/airvine/stac_fastapi

# # kill the old running instance
# pkill -f stac-fastapi-pgstac
# 
# #this assumes that there is a main.py file in the main directory that is used to set the custom rate limit
# as usual we are having workng directory issues. aborting for now
# nohup uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a stac.log & \
# while :; do sleep 3600; truncate -s 10M stac.log; done &
# sleep 5