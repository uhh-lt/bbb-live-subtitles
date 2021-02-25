import pymongo
import time
import redis
import json
import logging
import argparse

from multiprocessing import Manager

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
pubsub.subscribe("test_channel")

mydb = myclient["meteor"]["captions"]

# manager = Manager()
# u = manager.list()
# meeting = manager.dict()

last_subtitle = ""
# print(mydb)

def the_loop(debug):
    last_debug_line = ""
    last_subtitle = ""
    meetings = {}
    while True:
        fullmessage = pubsub.get_message()
        if fullmessage and not isinstance(fullmessage["data"], int):
            message = json.loads(fullmessage["data"].decode("UTF-8"))
            # print(message)
            if "Event" in message.keys():
                if message["Event"] == "KALDI_START":
                    logger.info("Kaldi is started. Lets get ASR!")
                    ASR = message["ASR-Channel"]
                    # print(ASR)
                    meetingId = message["meetingId"]
                    origCallerIDName = message["Caller-Orig-Caller-ID-Name"]
                    meetings = dict_handler(meetings, meetingId, ASR, origCallerIDName)
                    logger.debug(meetings)
                    pubsub.subscribe(ASR)
            if "handle" in message.keys():
                if message["handle"] == "partialUtterance":
                    # print(fullmessage)
                    # print(message)
                    channel = fullmessage["channel"].decode("utf-8")
                    meetingId = channel.split("%")[0]
                    speaker = message["speaker"]
                    # print(speaker)
                    utterance = message["utterance"]
                    id = get_meeting_pad(meetingId)
                    # print(id)
                    send_utterance(id, utterance, speaker) 
                if debug and (message["handle"] == "completeUtterance"):
                    if last_debug_line != utterance:
                        write_debug(debug, utterance)
                        last_debug_line = utterance



def write_debug(debug, utterance):
    with open(debug, "a+") as file:
        file.write(utterance + "\n")

def dict_handler(d, meetingId, ASR, participant):
    if ASR not in d.keys():
        d[meetingId] = {}
        d[meetingId]["participants"] = {}
    d[meetingId]["participants"][participant] = ""
    d[meetingId]["participants"]["ASR-Channel"] = ASR  # Wrong
    return d


def get_meeting_pad(meetingId):
    myquery = {"$and": [{"meetingId": meetingId}, {"locale.locale": "en"}]}
    v = mydb.find_one(myquery)
    # print(v)
    return v["_id"]
    # for i in mydb.find(myquery):
    #     print(i)


def send_utterance(Id, utterance, speaker):
    global last_subtitle
    if (len(utterance) == 0) or (utterance == "<UNK>"):
        pass
    elif last_subtitle != utterance:
        print(utterance)
        myquery = {"$and": [{"_id": Id}, {"locale.locale": "en"}]}
        v = mydb.find_one(myquery)
        revs = v["revs"]
        length = v["length"]
        subtitle = speaker + ": " + utterance + "\n"
        mydb.update({
            '_id': Id
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
    debug = args.debug
    the_loop(debug)
