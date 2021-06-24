import pymongo
import time
import redis
import json
import logging
# import argparse
from urllib import parse

from subtitles import subtitles

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

class mongodbconnector:

    def __init__(self):
        self.meetings = {}
        self.lastTimestamp = 0
        self.the_loop()

    def the_loop(self):
        meetings = self.meetings
        while True:
            fullmessage = pubsub.get_message()
            if fullmessage:
                event, textChannel, userId, voiceConf, meetingId, callerName, language, utterance = self.read_message(fullmessage)
                # print(fullmessage)
                if event == "VoiceCallStateEvtMsg~IN_CONFERENCE":
                    self.dict_handler(userId, callerName, language, voiceConf, meetingId)
                if event == "KALDI_START":  # TODO: Message to Redis
                    logger.info("Kaldi is started. Lets get ASR!")
                    self.dict_handler(userId, callerName, language, voiceConf, TextChannel=textChannel)
                    pubsub.subscribe(textChannel)
                if event == "KALDI_STOP":  # TODO: Message to Redis
                    logger.info("Kaldi is stopped. Unsubscribe channel")
                    pubsub.unsubscribe(textChannel)
                if event == "partialUtterance" or event == "completeUtterance":
                    meetings[voiceConf]["subtitles"].insert(userId=userId, callerName=callerName, utterance=utterance, event=event)
                    # print(meetings[voiceConf]["subtitles"].list())
                    # send_utterance(meetings, voiceConf, callerName, utterance)
                    self.send_subtitle(voiceConf)
            time.sleep(0.1)


    def read_message(self, fullmessage):
        """
        There are three main sources for messages: bbb-live-subtitles, BBB-core and kaldi-model-server.
        bbb-live-subtitles are mostly informations about the call (Event, Caller-Destination-Number, Caller-Orig-Caller-ID-Name, Caller-Username, Audio-Channel, Text-Channel, Control-Channel)
        BBB-core messages with an envelope and nested
        kaldi-model-server
        """
        event = textChannel = userId = voiceConf = meetingId = callerName = language = None
        utterance = ""
        message = json.loads(fullmessage["data"].decode("UTF-8"))

        if "Event" in message.keys():  # bbb-live-subtitle
            logger.debug(message)
            event = message["Event"]
            textChannel = message.get("Text-Channel")  # .get() returns None if is key not present
            userId = message["Caller-Orig-Caller-ID-Name"].split("-bbbID")[0]
            voiceConf = message["Caller-Destination-Number"]
            callerName = message["Caller-Username"]
            language = message.get("Language")
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
            if event == "partialUtterance" or event == "completeUtterance":
                logger.info(fullmessage)
                utterance = message["utterance"]
        
        # print(voiceConf)
        return event, textChannel, userId, voiceConf, meetingId, callerName, language, utterance


    def dict_handler(self, userId, callerName, language, voiceConf, meetingId=None, TextChannel=None, pad=None):
        d = self.meetings
        if voiceConf not in d.keys():
            d[voiceConf] = {}
            d[voiceConf]["userId"] = {}
            d[voiceConf]["subtitles"] = subtitles(voiceConf)
            if meetingId:
                print(meetingId)
                d[voiceConf]["meetingId"] = meetingId
            if TextChannel:
                d[voiceConf]["Text-Channel"] = TextChannel
        if userId not in d[voiceConf]["userId"].keys():
            d[voiceConf]["userId"][userId] = {}
            if TextChannel:
                d[voiceConf]["userId"][userId]["Text-Channel"] = TextChannel
            d[voiceConf]["userId"][userId]["callerName"] = callerName
            d[voiceConf]["userId"][userId]["language"] = language
        if pad:
            d[voiceConf]["pad"] = pad
        print(d)


    def check_chat(self, meetingId):
        lastTimestamp = self.lastTimestamp
        myquery2 = {"$and": [{"timestamp": { "$gt" : lastTimestamp}}, {"meetingId" : meetingId}]}
        mydb = myclient["meteor"]["group-chat-msg"]
        v = mydb.find(myquery2)
        for a in v:        
            if lastTimestamp < a["timestamp"]:
                lastTimestamp = a["timestamp"]
            if a == "PDFExport":
                return a
        return None


    def get_meeting_pad(self, meetingId):
        myquery = {"$and": [{"meetingId": meetingId}, {"locale.locale": "en"}]}
        v = mydb.find_one(myquery)
        if v is None:
            return None
        else:
            return v["_id"]
        # for i in mydb.find(myquery):
        #     print(i)


    def send_subtitle(self, voiceConf):
        meetings = self.meetings
        meetingId = meetings[voiceConf]["meetingId"]
        if "pad" not in meetings[voiceConf].keys():
            pad = self.get_meeting_pad(meetingId)
        else:
            pad = meetings[voiceConf]["pad"]

        if pad is None:  # bugfix when the conference ended but kaldi isn't fast enough
            return

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
    mongo = mongodbconnector()
    # the_loop()
