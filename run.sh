#!/bin/sh
tmux new-session \; \
  send-keys 'source env/bin/activate && python3 esl_to_redis.py' C-m \; \
  split-window -v \; \
  send-keys 'source env/bin/activate && python3 ws_receiver.py' C-m \; \
  split-window -h \; \
  send-keys 'source env/bin/activate && python3 mongodbconnector.py -s BBB_SERVER -c asr_channel -e ETHERPAD_API_KEY' C-m \;