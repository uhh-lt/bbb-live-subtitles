import asyncio
import websockets
import redis
import json
import logging
from urllib import parse

port = "3001"
asr_channel = "asr_channel"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

red = redis.Redis(host="localhost", port=6379, password="")


async def socket_to_redis(websocket, path):
    path = parse.unquote(path[1:])
    logger.info("Websocket Connection established")
    logger.info("Connected to: " + path)
    callerDestinationNumber = path.split("/")[0]
    origCallerIDName = path.split("/")[1]
    callerUsername = origCallerIDName.split("-bbbID-")[1]
    audioChannel = parse.quote(callerDestinationNumber + "~" + origCallerIDName) + "~audio"
    controlChannel = parse.quote(callerDestinationNumber + "~" + origCallerIDName) + "~control"
    textChannel = parse.quote(callerDestinationNumber + "~" + origCallerIDName) + "~text"
    redis_message("LOADER_START", callerDestinationNumber, origCallerIDName, callerUsername, audioChannel, controlChannel, textChannel)

    async for message in websocket:
        red.publish(audioChannel, message)
    logger.info("Connection %s closed" % path)
    redis_message("LOADER_STOP", callerDestinationNumber, origCallerIDName, callerUsername, audioChannel, controlChannel, textChannel)


def redis_message(event, callerDestinationNumber, origCallerIDName, callerUsername, audioChannel, controlChannel, textChannel):
    message = {
                "Event": event,
                "Caller-Destination-Number": callerDestinationNumber,
                "Caller-Orig-Caller-ID-Name": origCallerIDName,
                "Caller-Username": callerUsername,
                "Audio-Channel": audioChannel,
                "Control-Channel": controlChannel,
                "Text-Channel": textChannel,
              }
    logger.info(message)
    red.publish(asr_channel, json.dumps(message))


start_server = websockets.serve(socket_to_redis, "ltbbb2", port)

asyncio.get_event_loop().run_until_complete(start_server)
logger.info("Websocket Server started on Port " + port)
asyncio.get_event_loop().run_forever()
