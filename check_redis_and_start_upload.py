import redis
import json
import os
import multiprocessing as mp
import time
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

red = redis.Redis(host="localhost", port=6379, password="")
pubsub = red.pubsub()
data_channel = ["test_channel", "from-akka-apps-redis-channel"]

pubsub.subscribe(data_channel)

conferences = {}

loader = {}


def handle_loader():
    while True:
        message = pubsub.get_message()
        if message and message["data"] not in [1, 2]:
            message = json.loads(message["data"].decode("UTF-8"))
            try:
                if "Event" in message.keys():
                    mediaBugTarget = message["Media-Bug-Target"]
                    callerDestinationNumber = message["Caller-Destination-Number"]
                    origCallerIDName = message["Caller-Orig-Caller-ID-Name"]
                    callerUsername = message["Caller-Username"]
                    meetingId = conferences[callerDestinationNumber]
                    redisChannel = meetingId + "%" + callerUsername.replace(" ", ".") + "%asr"
                    if message["Event"] == "MEDIA_BUG_START":
                        logger.info("Media Bug Start")
                        logger.debug(message)
                        p = mp.Process(target=send_file_to_redis, args=(mediaBugTarget, redisChannel,))
                        p.start()
                        loader[mediaBugTarget] = p
                        loaderStartMsg = {
                                          "Event": "LOADER_START",
                                          "Caller-Destination-Number": callerDestinationNumber,
                                          "meetingId": meetingId,
                                          "Caller-Orig-Caller-ID-Name": origCallerIDName,
                                          "Caller-Username": callerUsername,
                                          "ASR-Channel": redisChannel
                                          }
                        red.publish(data_channel[0], json.dumps(loaderStartMsg))

                    if message["Event"] == "MEDIA_BUG_STOP":
                        logger.info("Media Bug Stop")
                        logger.debug(message)
                        p = loader.pop(mediaBugTarget, None)
                        if p:
                            p.terminate()
                            loaderStopMsg = {
                                        "Event": "LOADER_STOP",
                                        "Caller-Destination-Number": callerDestinationNumber,
                                        "meetingId": meetingId,
                                        "Caller-Orig-Caller-ID-Name": origCallerIDName,
                                        "Caller-Username": callerUsername,
                                        "ASR-Channel": redisChannel
                                        }
                            red.publish(data_channel[0], json.dumps(loaderStopMsg))
                            os.remove(mediaBugTarget)
                            # KMS needs two more data chunks to end definitely
                            time.sleep(0.5)
                            red.publish(redisChannel, 8*"\x00")
                            time.sleep(0.5)
                            red.publish(redisChannel, 8*"\x00")

                if "envelope" in message.keys():
                    if message["envelope"]["name"] == "VoiceCallStateEvtMsg":
                        logger.info("VoiceCallStateEvtMsg")
                        logger.debug(message)
                        message = message["core"]["body"]
                        voiceConf = message["voiceConf"]
                        meetingId = message["meetingId"]
                        conferences[voiceConf] = meetingId

            except:
                pass


def send_file_to_redis(filename, channel, chunksize=2048*2):
    # Open the file
    file = open(filename, 'rb', buffering=chunksize)
    logger.debug("Opened File: " + filename)
    # Find the actual size of the file and move to the end
    st_results = os.stat(filename)
    st_size = st_results[6]
    file.seek(st_size)

    while True:
        last_read_pos = file.tell()
        line = file.read(chunksize)
        if line:
            logger.debug("Read chunk of:" + str(len(line)) + "bytes.")
            red.publish(channel, line)
        else:
            time.sleep(0.1281)
            file.seek(last_read_pos)


if __name__ == "__main__":
    mp.get_context("spawn")
    handle_loader()
