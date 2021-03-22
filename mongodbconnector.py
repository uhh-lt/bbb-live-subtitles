import pymongo
# import time
import redis
import json
import logging
import argparse
from urllib import parse

myclient = pymongo.MongoClient("mongodb://127.0.1.1:27017")

logging.basicConfig(
    level=logging.DEBUG,
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
            if event == "KALDI_START": # TODO: Message to Redis
                logger.info("Kaldi is started. Lets get ASR!")
                meetings = dict_handler(meetings, userId, callerName, voiceConf, TextChannel=textChannel)
                pubsub.subscribe(textChannel)
            if event == "KALDI_STOP": # TODO: Message to Redis
                logger.info("Kaldi is stopped. Unsubscribe channel")
                pubsub.unsubscribe(textChannel)
            if event == "partialUtterance":
                send_utterance(meetings, voiceConf, utterance, callerName)


def read_message(fullmessage):
    """
    There are three main sources for messages: BBB-core, bbb-live-subtitles and kaldi-model-server.
    
    """
    event = textChannel = userId = voiceConf = meetingId = callerName = None
    utterance = ""
    message = json.loads(fullmessage["data"].decode("UTF-8"))
    logger.debug(message)
    if "Event" in message.keys():
        event = message["Event"]
        if "Text-Channel" in message.keys():
            textChannel = message["Text-Channel"]
        userId = message["Caller-Orig-Caller-ID-Name"].split("-bbbID")[0]
        voiceConf = message["Caller-Destination-Number"]
        callerName = message["Caller-Username"]
    if "core" in message.keys() and "header" in message["core"].keys() and "body" in message["core"].keys(): # BBB messages
        message = message["core"]
        if "name" in message["header"].keys() and "body" in message.keys() and "callState" in message["body"].keys():
            event = message["header"]["name"] + "~" + message["body"]["callState"]
            userId = message["body"]["userId"]
            voiceConf = message["body"]["voiceConf"]
            meetingId = message["header"]["meetingId"]
            callerName = message["body"]["callerName"]
    if "handle" in message.keys():
        event = message["handle"]
        voiceConf = parse.unquote(fullmessage["channel"].decode("utf-8")).split("~")[0]
        if "speaker" in message.keys():
            callerName = message["speaker"]
        if event == "partialUtterance":
            utterance = message["utterance"]

    return event, textChannel, userId, voiceConf, meetingId, callerName, utterance


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
    print("hi")
    print(last_subtitle)
    meetingId = meetings[voiceConf]["meetingId"]
    print(meetingId)
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
        logger.debug(utterance)
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
