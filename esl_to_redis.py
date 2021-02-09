from jaspion import Jaspion
import redis
import json
import logging
import argparse

# TODO: Add parameter to both
app = Jaspion(host='127.0.0.1', port=8021, password='042f799c91402289')

red = redis.Redis(host="localhost", port=6379, password="")

logging.basicConfig()
logger = logging.getLogger("ESL-Bridge")
logger.setLevel(logging.DEBUG)

# TODO:Add Heartbeat to check if the connection is lost


@app.handle('MEDIA_BUG_START')
def media_bug_start(event):
    logger.info("MEDIA_BUG_START")
    logger.debug(event)
    callerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
    Event = event["Event-Name"]
    origCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    mediaBugTarget = event["Media-Bug-Target"]
    mediaBugFunction = event["Media-Bug-Function"]
    callerUsername = origCallerIDName.partition("-bbbID-")[2]
    if mediaBugFunction == "session_record":
        start_MB = {"Event": Event, "Caller-Destination-Number": callerDestinationNumber, "Caller-Orig-Caller-ID-Name": origCallerIDName, "Caller-Username": callerUsername, "Media-Bug-Target": mediaBugTarget}
        send_to_pubsub(start_MB)


@app.handle('MEDIA_BUG_STOP')
def media_bug_stop(event):
    logger.info("MEDIA_BUG_STOP")
    logger.debug(event)
    CallerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
    Event = event["Event-Name"]
    OrigCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    Media_Bug_Target = event["Media-Bug-Target"]
    Media_Bug_Function = event["Media-Bug-Function"]
    CallerUsername = OrigCallerIDName.partition("-bbbID-")[2]

    if Media_Bug_Function == "session_record":
        stop_MB = {"Event": Event, "Caller-Destination-Number": CallerDestinationNumber, "Caller-Orig-Caller-ID-Name": OrigCallerIDName, "Caller-Username": CallerUsername, "Media-Bug-Target": Media_Bug_Target}
        send_to_pubsub(stop_MB)


def send_to_pubsub(data):
    logger.debug(data)
    data = json.dumps(data)
    red.publish("test_channel", data)


if __name__ == '__main__':
    # Argument Parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-s", "--server", help="REDIS Pubsub Server hostname or IP")
    parser.add_argument("-c", "--channel", help="The Pubsub Information Channel")
    parser.add_argument("-fs", "--freeswitchServer", help="Freeswitch Server hostname or IP")
    parser.add_argument("-fp", "--freeswitchPassword", help="Freeswitch Password")
