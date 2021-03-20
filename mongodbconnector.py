import pymongo
# import time
import redis
import json
import logging
import argparse

# from multiprocessing import Manager

myclient = pymongo.MongoClient("mongodb://127.0.1.1:27017")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# REDIS #
red = redis.Redis(host="localhost", port=6379, password="")
pubsub = red.pubsub()
pubsub.subscribe("asr_channel", "from-akka-apps-redis-channel")

mydb = myclient["meteor"]["captions"]

# manager = Manager()
# u = manager.list()
# meeting = manager.dict()
last_subtitle = ""


def the_loop():
    meetings = {}
    while True:
        fullmessage = pubsub.get_message()
        if fullmessage and not isinstance(fullmessage["data"], int):
            message = json.loads(fullmessage["data"].decode("UTF-8"))
            # print(message)
            if "core" in message.keys():
                if message["core"]["header"]["name"] == "VoiceCallStateEvtMsg" and message["core"]["body"]["callState"] == "IN_CONFERENCE":
                    print(message)
                    meetingId = message["core"]["header"]["meetingId"]
                    voiceConf = message["core"]["body"]["voiceConf"]
                    userId = message["core"]["body"]["userId"]
                    callerName = message["core"]["body"]["callerName"]
                    meetings = dict_handler(meetings, userId, callerName, voiceConf, meetingId)
            if "Event" in message.keys():
                if message["Event"] == "KALDI_START":
                    logger.info("Kaldi is started. Lets get ASR!")
                    print(message)
                    TextChannel = message["Text-Channel"]
                    userId = message["Caller-Orig-Caller-ID-Name"].split("-bbbID")[0]
                    voiceConf = message["Caller-Destination-Number"]
                    callerName = message["Caller-Username"]
                    meetings = dict_handler(meetings, userId, callerName, voiceConf, TextChannel)
                    pubsub.subscribe(TextChannel)
            if "handle" in message.keys():
                # print(fullmessage)
                if message["handle"] == "partialUtterance":
                    print(fullmessage)
                    print(message)
                    channel = fullmessage["channel"].decode("utf-8")
                    voiceConf = channel.split("%%")[0]
                    speaker = message["speaker"]
                    utterance = message["utterance"]
                    send_utterance(meetings, voiceConf, utterance, speaker)

def dict_handler(d: dict, userId, callerName, voiceConf, meetingId=None, TextChannel=None, pad=None):
    if voiceConf not in d.keys():
        d[voiceConf] = {}
        d[voiceConf]["userId"] = {}
        if meetingId:
            d[voiceConf]["meetingId"] = meetingId
        if TextChannel:
            d[voiceConf]["Text-Channel"] = TextChannel
    if userId not in d[voiceConf]["userId"].keys():
        d[voiceConf]["userId"][userId] = {}
        if TextChannel:
            d[voiceConf]["userId"][userId]["Text-Channel"] = TextChannel
        d[voiceConf]["userId"][userId]["callerName"] = callerName
    if pad:
        d[voiceConf]["pad"] = pad

    return d

def get_meeting_pad(meetingId):
    myquery = {"$and": [{"meetingId": meetingId}, {"locale.locale": "en"}]}
    v = mydb.find_one(myquery)
    # print(v)
    return v["_id"]
    # for i in mydb.find(myquery):
    #     print(i)

def send_utterance(meetings: dict, voiceConf, utterance, speaker):
    global last_subtitle
    meetingId = meetings[voiceConf]["meetingId"]
    # print(meetings[voiceConf]["pad"])
    if "pad" not in meetings[voiceConf].keys():
        pad = get_meeting_pad(meetingId)
    else:
        pad = meetings[voiceConf]["pad"]

    utterance = utterance.replace("<UNK>", "").replace("wow", "").replace("ähm", "").replace("äh", "") # removes hesitations and <UNK> Token
    utterance = " ".join(utterance.split()) # removes multiples spaces
    if (len(utterance) == 0):
        pass
    elif last_subtitle != utterance:
        print(utterance)
        myquery = {"$and": [{"_id": pad}, {"locale.locale": "en"}]}
        v = mydb.find_one(myquery)
        revs = v["revs"]
        length = v["length"]
        subtitle = speaker + ": " + utterance + "\n"
        mydb.update({
            '_id': pad
        }, {
            '$set': {
                'data': subtitle,
                'revs': revs + 1,
                'length': length + 1
            }
        }, upsert=False
        )
        last_subtitle = utterance


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-d", "--debug", help="Filename for debug output")
    args = parser.parse_args()
    the_loop()
