from jaspion import Jaspion
from jaspion.utils import filtrate
import redis
import json
import logging
import argparse
from urllib import parse

server = "ltbbb2"
ws_port = "3001"
asr_channel = "asr_channel"

# TODO: Add parameter to both
app = Jaspion(host='127.0.0.1', port=8021, password='042f799c91402289')
red = redis.Redis(host="localhost", port=6379, password="")

logging.basicConfig()
logger = logging.getLogger("ESL-Bridge")
logger.setLevel(logging.DEBUG)


@app.handle('conference::maintenance')
@filtrate('Action', 'add-member')
def add_member(event):
    logger.info("add-member")
    # logger.debug(event)
    uuid = event["Unique-ID"]
    Event = "add-member"
    callerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
    CallerOrigCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    CallerID = CallerOrigCallerIDName.partition("-bbbID-")[0]
    callerUsername = CallerOrigCallerIDName.partition("-bbbID-")[2]
    socket_adress = "ws://" + server + ":" + ws_port + "/" + \
                    callerDestinationNumber + "/" + \
                    parse.quote(CallerOrigCallerIDName)
    app.command(command="uuid_audio_fork " + uuid + " start " + socket_adress + " mono 16k", background=False)

    add_member = {
                  "Event": Event,
                  "Caller-Destination-Number": callerDestinationNumber,
                  "Caller-Orig-Caller-ID-Name": CallerOrigCallerIDName,
                  "Caller-ID": CallerID,
                  "Caller-Username": callerUsername,
                  "UUID": uuid
                 }
    send_to_pubsub(add_member)


@app.handle('mod_audio_fork::connect')
def mod_audio_fork_connect(event):
    logger.info("mod_audio_fork::connect")
    # logger.debug(event)
    # uuid = event["Unique-ID"]
    Event = "mod_audio_fork::connect"
    callerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
    origCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    callerUsername = origCallerIDName.partition("-bbbID-")[2]

    maf_connect = {
                    "Event": Event,
                    "Caller-Destination-Number": callerDestinationNumber,
                    "Caller-Orig-Caller-ID-Name": origCallerIDName,
                    "Caller-Username": callerUsername,
                  }
    send_to_pubsub(maf_connect)


@app.handle('conference::maintenance')  # TODO
@filtrate('Action', 'del-member')
def del_member(event):
    print(event)


# TODO:Add Heartbeat to check if the connection is lost

# Could be a event to send commands with
# @app.handle('RECV_RTCP_MESSAGE')
# def hb(event):
#     print(event)
#     app.command(command="uuid_audio_fork " + uuid + " start ws://localhost:3001 mono 16k teeeeest", background=False)

def send_to_pubsub(data):
    logger.debug("Redis Message to " + asr_channel + " :")
    logger.debug(data)
    data = json.dumps(data)
    red.publish(asr_channel, data)


if __name__ == '__main__':
    # Argument Parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-s", "--server", help="REDIS Pubsub Server hostname or IP")
    parser.add_argument("-c", "--channel", help="The Pubsub Information Channel")
    parser.add_argument("-fs", "--freeswitchServer", help="Freeswitch Server hostname or IP")
    parser.add_argument("-fp", "--freeswitchPassword", help="Freeswitch Password")

    app.run()
