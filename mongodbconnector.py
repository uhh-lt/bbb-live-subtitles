import pymongo
import time
import redis
import json
import logging
import argparse
from py_etherpad import EtherpadLiteClient

# import argparse
from urllib import parse

from subtitles import subtitles

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

class mongodbconnector:

    def __init__(self, etherpadKey, asrChannel, redisHost, mongodbHost = '127.0.1.1:27017'):
        # MongoDB
        self.myclient = pymongo.MongoClient('mongodb://' + mongodbHost)
        self.mydb = self.myclient['meteor']['captions']
        # REDIS
        red = redis.Redis(host=redisHost, port=6379, password='')
        self.pubsub = red.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(asrChannel, 'from-akka-apps-redis-channel', 'to-voice-conf-redis-channel')
        
        # Etherpad
        self.etherpadKey= etherpadKey
        self.myPad = EtherpadLiteClient(self.etherpadKey)

        self.meetings = {}
        self.lastTimestamp = 0
        self.message = {}

        self.the_loop()
        

    def the_loop(self):
        while True:
            fullmessage = self.pubsub.get_message()
            if fullmessage:
                self.read_message(fullmessage)
                message = self.message
                event = message.get('event')
                if event == 'AddPadEvtMsg':
                    if len(message['etherPadId'].split('_')) == 1:
                        self.dict_handler()
                        self.firstMessage()
                if event == 'VoiceCallStateEvtMsg~IN_CONFERENCE':
                    self.dict_handler()
                if event == 'GetUsersInVoiceConfSysMsg':
                    self.dict_handler()
                if event == 'KALDI_START':  # TODO: Message to Redis
                    logger.info('Kaldi is started. Lets get ASR!')
                    self.dict_handler()
                    self.pubsub.subscribe(message['textChannel'])
                if event == 'KALDI_STOP':  # TODO: Message to Redis
                    logger.info('Kaldi is stopped. Unsubscribe channel')
                    self.pubsub.unsubscribe(message['textChannel'])
                if event == 'partialUtterance' or event == 'completeUtterance':
                    voiceConf = message['voiceConf']
                    userId = message['userId']
                    callerName = message['callerName']
                    utterance = message['utterance']
                    meetingId = self.get_meetingId(voiceConf)
                    self.meetings[meetingId]['subtitles'].insert(userId=userId, callerName=callerName, utterance=utterance, event=event)
                    self.send_subtitle(meetingId)
                    self.appendEtherPad()
                self.message = {}
            time.sleep(0.1)
                

    def firstMessage(self):
        meetingId = self.message["meetingId"]
        etherPadId = self.meetings[meetingId]['etherPadId']
        myPad = self.myPad

        myPad.appendText(etherPadId, '\r\n\r\n\r\n\r\n-----\r\nUntertitel:\r\n-----\r\n')

    def appendEtherPad(self):
        voiceConf = self.message['voiceConf']
        meetingId = self.get_meetingId(voiceConf)
        etherPadId = self.meetings[meetingId]['etherPadId']
        subtitles = self.meetings[meetingId]['subtitles']
        utterance = subtitles.latest()
        myPad = self.myPad
        if utterance:
            for utt in utterance:
                myPad.appendText(etherPadId, utt + '\r\n')
        
    def read_message(self, fullmessage):
        '''
        There are main sources for messages: bbb-live-subtitles, BBB-core, from-etherpad-redis-channel and kaldi-model-server.
        bbb-live-subtitles are mostly informations about the call (Event, Caller-Destination-Number, Caller-Orig-Caller-ID-Name, Caller-Username, Audio-Channel, Text-Channel, Control-Channel)
        BBB-core and from-etherpad-redis-channel are with an envelope and nested
        kaldi-model-server
        '''
        message = {}
        messageJson = json.loads(fullmessage['data'].decode('UTF-8'))
        # print(messageJson)
        if 'Event' in messageJson.keys():  # bbb-live-subtitle
            logger.debug(message)                    
            message['event'] = messageJson['Event']
            message['textChannel'] = messageJson.get('Text-Channel')  # .get() returns None if is key not present
            message['userId'] = messageJson['Caller-Orig-Caller-ID-Name'].split('-bbbID')[0]
            message['voiceConf'] = messageJson['Caller-Destination-Number']
            message['callerName'] = messageJson['Caller-Username']
            message['language'] = message.get('Language')
        if 'core' in messageJson.keys() and 'header' in messageJson['core'].keys() and 'body' in messageJson['core'].keys():  # BBB from-akka-apps-redis-channel messages
            messageJson = messageJson['core']
            if 'name' in messageJson['header'].keys() and 'body' in messageJson.keys():
                if 'callState' in messageJson['body'].keys():
                    logger.info(messageJson)
                    message['event'] = messageJson['header']['name'] + '~' + messageJson['body']['callState']
                    message['userId'] = messageJson['body']['userId']
                    message['voiceConf'] = messageJson['body']['voiceConf']
                    message['meetingId'] = messageJson['header']['meetingId']
                    message['callerName'] = messageJson['body']['callerName']
                elif (messageJson['header']['name'] == 'AddPadEvtMsg'): # Meeting is created
                    # print('grützi!')
                    message['event'] = messageJson['header']['name']
                    message['meetingId'] = messageJson['header']['meetingId']
                    message['etherPadId'] = messageJson['body']['padId']
        if 'handle' in messageJson.keys():  # kaldi-model-server messages
            message['event'] = messageJson['handle']
            fullmessage = parse.unquote(fullmessage['channel'].decode('utf-8'))
            message['voiceConf'] = fullmessage.split('~')[0]
            message['userId'] = fullmessage.split('~')[1].split('-bbbID-')[0]
            message['callerName'] = messageJson.get('speaker')
            if message['event'] == 'partialUtterance' or message['event'] == 'completeUtterance':
                logger.info(fullmessage)
                message['utterance'] = messageJson['utterance']
        if 'header' in messageJson.keys():
            if messageJson['header']['name'] == 'GetUsersInVoiceConfSysMsg':
                message['event'] = messageJson['header']['name']
                message['meetingId'] = messageJson['header']['meetingId']
                message['voiceConf'] = messageJson['body']['voiceConf']
        
        self.message = message
        # print(voiceConf)
        # return event, textChannel, userId, voiceConf, meetingId, callerName, language, utterance

    def get_meetingId(self, voiceConf):
        d = self.meetings
    
        for a in d:
            if d[a]['voiceConf'] == voiceConf:
                return a
        return None
    
    def dict_handler(self):
        message = self.message
        userId = message.get('userId')
        callerName = message.get('callerName')
        language = message.get('language')
        voiceConf = message.get('voiceConf')
        meetingId = message.get('meetingId')
        textChannel = message.get('textChannel')
        mongoDbPad = message.get('pad')
        etherPadId = message.get('etherPadId')

        if userId and userId[-3] == '_': # BBB counts the last Ids up sometimes
            userId = userId[:-3]

        d = self.meetings
        if meetingId and meetingId not in d.keys():
            d[meetingId] = {}
            d[meetingId]['userId'] = {}
            d[meetingId]['subtitles'] = subtitles(meetingId)
            if voiceConf:
                d[meetingId]['voiceConf'] = voiceConf
            # if textChannel:
            #     d[meetingId]['Text-Channel'] = textChannel
        if userId and not meetingId:
            meetingId = self.get_meetingId(voiceConf)
        if meetingId and userId and userId not in d[meetingId]['userId'].keys():
            d[meetingId]['userId'][userId] = {}
            if textChannel:
                d[meetingId]['userId'][userId]['Text-Channel'] = textChannel
            d[meetingId]['userId'][userId]['callerName'] = callerName
            d[meetingId]['userId'][userId]['language'] = language
        if mongoDbPad:
            d[meetingId]['mongoDbPad'] = mongoDbPad
        if etherPadId:
            d[meetingId]['etherPadId'] = etherPadId

    def dict_handler2(self):
        message = self.message
        userId = message.get('userId')
        callerName = message.get('callerName')
        language = message.get('language')
        voiceConf = message.get('voiceConf')
        meetingId = message.get('meetingId')
        textChannel = message.get('textChannel')
        mongoDbPad = message.get('pad')
        etherPadId = message.get('etherPadId')

        d = self.meetings
        print('print d')
        print(d)
        if voiceConf not in d.keys():
            d[voiceConf] = {}
            d[voiceConf]['userId'] = {}
            d[voiceConf]['subtitles'] = subtitles(voiceConf)
            if meetingId:
                d[voiceConf]['meetingId'] = meetingId
            if textChannel:
                d[voiceConf]['Text-Channel'] = textChannel
        if userId not in d[voiceConf]['userId'].keys():
            d[voiceConf]['userId'][userId] = {}
            if textChannel:
                d[voiceConf]['userId'][userId]['Text-Channel'] = textChannel
            d[voiceConf]['userId'][userId]['callerName'] = callerName
            d[voiceConf]['userId'][userId]['language'] = language
        if mongoDbPad:
            d[voiceConf]['mongoDbPad'] = mongoDbPad
        if etherPadId:
            d[voiceConf]['etherPadId'] = etherPadId

    def get_meeting_pad(self, meetingId):
        myquery = {'$and': [{'meetingId': meetingId}, {'locale.locale': 'de'}]}
        v = self.mydb.find_one(myquery)
        if v is None:
            return None
        else:
            return v['_id']
        # for i in mydb.find(myquery):
        #     print(i)


    def send_subtitle(self, meetingId):
        meetings = self.meetings
        # voiceConf = meetings[meetingId]['voiceConf']
        if 'mongoDbPad' not in meetings[meetingId].keys():
            mongoDbPad = self.get_meeting_pad(meetingId)
        else:
            mongoDbPad = meetings[meetingId]['mongoDbPad']

        if mongoDbPad is None:  # bugfix when the conference ended but kaldi isn't fast enough
            return

        subtitles = meetings[meetingId]['subtitles']

        subtitle = subtitles.show()
        print(subtitle)
        if subtitle is not None:
            logger.debug(subtitle)
            myquery = {'$and': [{'_id': mongoDbPad}, {'locale.locale': 'de'}]}
            v = self.mydb.find_one(myquery)
            revs = v['revs']
            length = v['length']
            self.mydb.update({
                '_id': mongoDbPad
            }, {
                '$set': {
                    'data': subtitle,
                    'revs': revs + 1,
                    'length': length + 1
                }
            }, upsert=False
            )


if __name__ == '__main__':
    # Argument Parser
    parser = argparse.ArgumentParser()

    # # flag (- and --) arguments
    parser.add_argument('-s', '--server', help='REDIS Pubsub Server hostname or IP', default='localhost')
    parser.add_argument('-c', '--channel', help='The Pubsub Information Channel', default='asr_channel')
    parser.add_argument('-e', '--etherpadKey', help='etherpad API Key', required=True)
    args = parser.parse_args()
    mongo = mongodbconnector(etherpadKey=args.etherpadKey, asrChannel=args.channel, redisHost=args.server)
