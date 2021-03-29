import pymongo
import time
import redis
import json
import logging
import argparse
from urllib import parse
from collections import OrderedDict

from subtitles import subtitles

myclient = pymongo.MongoClient("mongodb://127.0.1.1:27017")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# REDIS #
red = redis.Redis(host="localhost", port=6379, password="")
pubsub = red.pubsub(ignore_subscribe_messages=True)
pubsub.subscribe("asr_channel", "from-akka-apps-redis-channel")

mydb = myclient["meteor"]["captions"]

last_subtitle = ""


def the_loop():
    meetings = {}
    while True:
        fullmessage = pubsub.get_message()
        if fullmessage:
            event, textChannel, userId, voiceConf, meetingId, callerName, utterance = read_message(fullmessage)
            if event == "VoiceCallStateEvtMsg~IN_CONFERENCE":
                meetings = dict_handler(meetings, userId, callerName, voiceConf, meetingId)
            if event == "KALDI_START":  # TODO: Message to Redis
                logger.info("Kaldi is started. Lets get ASR!")
                meetings = dict_handler(meetings, userId, callerName, voiceConf, TextChannel=textChannel)
                pubsub.subscribe(textChannel)
            if event == "KALDI_STOP":  # TODO: Message to Redis
                logger.info("Kaldi is stopped. Unsubscribe channel")
                pubsub.unsubscribe(textChannel)
            if event == "partialUtterance" or event == "completeUtterance":
                meetings[voiceConf]["subtitles"].insert(userId=userId, callerName=callerName, utterance=utterance)
                print(meetings[voiceConf]["subtitles"].list())
                # send_utterance(meetings, voiceConf, callerName, utterance)
                send_subtitle(meetings, voiceConf)


def read_message(fullmessage):
    """
    There are three main sources for messages: bbb-live-subtitles, BBB-core and kaldi-model-server.
    bbb-live-subtitles are mostly informations about the call (Event, Caller-Destination-Number, Caller-Orig-Caller-ID-Name, Caller-Username, Audio-Channel, Text-Channel, Control-Channel)
    BBB-core messages with an envelope and nested
    kaldi-model-server
    """
    event = textChannel = userId = voiceConf = meetingId = callerName = None
    utterance = ""
    message = json.loads(fullmessage["data"].decode("UTF-8"))

    if "Event" in message.keys():  # bbb-live-subtitle
        logger.debug(message)
        event = message["Event"]
        textChannel = message.get("Text-Channel")  # .get() returns None if is key not present
        userId = message["Caller-Orig-Caller-ID-Name"].split("-bbbID")[0]
        voiceConf = message["Caller-Destination-Number"]
        callerName = message["Caller-Username"]
    if "core" in message.keys() and "header" in message["core"].keys() and "body" in message["core"].keys():  # BBB-core
        message = message["core"]
        if "name" in message["header"].keys() and "body" in message.keys() and "callState" in message["body"].keys():
            logger.info(message)
            event = message["header"]["name"] + "~" + message["body"]["callState"]
            userId = message["body"]["userId"]
            voiceConf = message["body"]["voiceConf"]
            meetingId = message["header"]["meetingId"]
            callerName = message["body"]["callerName"]
    if "handle" in message.keys():  # kaldi-model-server
        event = message["handle"]
        fullmessage = parse.unquote(fullmessage["channel"].decode("utf-8"))
        voiceConf = fullmessage.split("~")[0]
        userId = fullmessage.split("~")[1].split("-bbbID-")[0]
        callerName = message.get("speaker")
        if event == "partialUtterance":
            logger.info(fullmessage)
            utterance = message["utterance"]

    return event, textChannel, userId, voiceConf, meetingId, callerName, utterance


def dict_handler(d: dict, userId, callerName, voiceConf, meetingId=None, TextChannel=None, pad=None):
    if voiceConf not in d.keys():
        d[voiceConf] = {}
        d[voiceConf]["userId"] = {}
        d[voiceConf]["subtitles"] = subtitles(voiceConf)
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


def send_utterance(meetings: dict, voiceConf, callerName, utterance):
    global last_subtitle
    meetingId = meetings[voiceConf]["meetingId"]
    if "pad" not in meetings[voiceConf].keys():
        pad = get_meeting_pad(meetingId)
    else:
        pad = meetings[voiceConf]["pad"]
    utterance = utterance.replace("<UNK>", "").replace("wow", "").replace("ähm", "").replace("äh", "")  # removes hesitations and <UNK> Token
    utterance = " ".join(utterance.split())  # removes multiples spaces
    if (len(utterance) == 0):
        pass
    elif last_subtitle != utterance:
        logger.debug(utterance)
        myquery = {"$and": [{"_id": pad}, {"locale.locale": "en"}]}
        v = mydb.find_one(myquery)
        revs = v["revs"]
        length = v["length"]
        subtitle = callerName + ": " + utterance + "\n"
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


def store_subtitle(meetings: dict, userId, voiceConf, callerName, utterance, priority=0):
    actualTime = time.time()
    subtitles = meetings[voiceConf]["subtitles"]
    utterance = utterance.replace("<UNK>", "").replace("wow", "").replace("ähm", "").replace("äh", "")  # removes hesitations and <UNK> Token
    utterance = " ".join(utterance.split())  # removes multiples spaces

    if len(utterance) > 1:
        subtitles[userId] = {
                              "callerName": callerName,
                              "subtitle": utterance,
                              "time": actualTime,
                              "priority": priority
                            }

    new_subtitles = OrderedDict()
    for key, value in subtitles.items():
        if actualTime - value["time"] < 4:
            new_subtitles[key] = value
    meetings[voiceConf]["subtitles"] = new_subtitles
    return meetings


def send_subtitle(meetings: dict, voiceConf):
    meetingId = meetings[voiceConf]["meetingId"]
    if "pad" not in meetings[voiceConf].keys():
        pad = get_meeting_pad(meetingId)
    else:
        pad = meetings[voiceConf]["pad"]

    subtitles = meetings[voiceConf]["subtitles"]

    subtitle = subtitles.show()
    print(subtitle)
    if subtitle is not None:
        logger.debug(subtitle)
        myquery = {"$and": [{"_id": pad}, {"locale.locale": "en"}]}
        v = mydb.find_one(myquery)
        revs = v["revs"]
        length = v["length"]
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


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-d", "--debug", help="Filename for debug output")
    args = parser.parse_args()
    the_loop()
