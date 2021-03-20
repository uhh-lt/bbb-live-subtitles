from jaspion import Jaspion
from jaspion.utils import filtrate
import redis
import json
import logging
import argparse

server = "ltbbb2"
ws_port = "3001"


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
    origCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    # origCallerID = origCallerIDName.partition("-bbbID-")[0]
    callerUsername = origCallerIDName.partition("-bbbID-")[2]
    print(callerUsername)
    print(origCallerIDName)
    # print(uuid)
    
    socket_adress = "ws://" + server + ":" + ws_port + "/" + callerDestinationNumber + "%%" + origCallerIDName.replace("-", "%35")
    app.command(command="uuid_audio_fork " + uuid + " start " + socket_adress + " mono 16k", background=False)
    
    add_member = {  "Event": Event,
                    "Caller-Destination-Number": callerDestinationNumber,
                    "Caller-Orig-Caller-ID-Name": origCallerIDName,
                    "Caller-Username": callerUsername,
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

    maf_connect = { "Event": Event,
                    "Caller-Destination-Number": callerDestinationNumber,
                    "Caller-Orig-Caller-ID-Name": origCallerIDName,
                    "Caller-Username": callerUsername,
                 }
    send_to_pubsub(maf_connect)

@app.handle('conference::maintenance')
@filtrate('Action', 'del-member')
def del_member(event):
    print(event)


# TODO:Add Heartbeat to check if the connection is lost

# Could be a event to send commands with
# @app.handle('RECV_RTCP_MESSAGE')
# def hb(event):
#     print(event)
#     app.command(command="uuid_audio_fork " + uuid + " start ws://localhost:3001 mono 16k teeeeest", background=False)

# @app.handle('MEDIA_BUG_START')
# def media_bug_start(event):
#     logger.info("MEDIA_BUG_START")
#     logger.debug(event)
#     callerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
#     Event = event["Event-Name"]
#     origCallerIDName = event["Caller-Orig-Caller-ID-Name"]
#     mediaBugTarget = event["Media-Bug-Target"]
#     mediaBugFunction = event["Media-Bug-Function"]
#     callerUsername = origCallerIDName.partition("-bbbID-")[2]
#     if mediaBugFunction == "session_record":
#         start_MB = {"Event": Event,
#                     "Caller-Destination-Number": callerDestinationNumber,
#                     "Caller-Orig-Caller-ID-Name": origCallerIDName,
#                     "Caller-Username": callerUsername,
#                     "Media-Bug-Target": mediaBugTarget}
#         send_to_pubsub(start_MB)


# @app.handle('MEDIA_BUG_STOP')
# def media_bug_stop(event):
    # logger.info("MEDIA_BUG_STOP")
    # # logger.debug(event)
    # CallerDestinationNumber = event["Caller-Destination-Number"].replace("echo", "")
    # Event = event["Event-Name"]
    # OrigCallerIDName = event["Caller-Orig-Caller-ID-Name"]
    # Media_Bug_Target = event["Media-Bug-Target"]
    # Media_Bug_Function = event["Media-Bug-Function"]
    # CallerUsername = OrigCallerIDName.partition("-bbbID-")[2]

    # if Media_Bug_Function == "session_record":
    #     stop_MB = {"Event": Event, "Caller-Destination-Number": CallerDestinationNumber, "Caller-Orig-Caller-ID-Name": OrigCallerIDName, "Caller-Username": CallerUsername, "Media-Bug-Target": Media_Bug_Target}
    #     send_to_pubsub(stop_MB)


def send_to_pubsub(data):
    logger.debug(data)
    data = json.dumps(data)
    red.publish("asr_channel", data)

if __name__ == '__main__':
    # Argument Parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-s", "--server", help="REDIS Pubsub Server hostname or IP")
    parser.add_argument("-c", "--channel", help="The Pubsub Information Channel")
    parser.add_argument("-fs", "--freeswitchServer", help="Freeswitch Server hostname or IP")
    parser.add_argument("-fp", "--freeswitchPassword", help="Freeswitch Password")

    app.run()
