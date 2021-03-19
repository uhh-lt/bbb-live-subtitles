import asyncio
import websockets
import redis
import json
import os
import multiprocessing as mp
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

red = redis.Redis(host="localhost", port=6379, password="")

async def socket_to_redis(websocket, path):
    logger.info("Websocket Connection established")
    path = path[1:]
    logger.info("Connected to: " + path)
    callerDestinationNumber = path.split("%%")[0] # %% marks the split between conference ID and CallerIDName
    origCallerIDName = path.split("%%")[1].replace("%35", "-")  # %35 is a minus (-) sign in (ASCII) 
    callerUsername = path.replace("%35", "-").split("-bbbID-")[1]   
    controlChannel = path + "%control"
    loaderStartMsg = {
                        "Event": "LOADER_START",
                        "Caller-Destination-Number": callerDestinationNumber,
                        "Caller-Orig-Caller-ID-Name": origCallerIDName,
                        "Caller-Username": callerUsername,
                        "Audio-Channel": path + "%audio", 
                        "Control-Channel": controlChannel,
                        "Text-Channel": path + "%text",
                     }
    red.publish("asr_channel", json.dumps(loaderStartMsg))
    async for message in websocket:
        red.publish(path + "%audio", message)
    logger.info("Connection %s closed" % path)
    loaderStopMsg = {
                        "Event": "LOADER_STOP",
                        "Caller-Destination-Number": callerDestinationNumber,
                        "Caller-Orig-Caller-ID-Name": origCallerIDName,
                        "Caller-Username": callerUsername,
                        "Audio-Channel": path + "%audio", 
                        "Control-Channel": controlChannel,
                        "Text-Channel": path + "%text",
                     }
    red.publish("asr_channel", json.dumps(loaderStopMsg))

start_server = websockets.serve(socket_to_redis, "ltbbb2", 3001)

asyncio.get_event_loop().run_until_complete(start_server)
logger.info("Websocket Server started")
asyncio.get_event_loop().run_forever()