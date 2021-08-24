import asyncio
import websockets
import redis
import json
import logging
import time
from threading import Thread
from urllib import parse

port = '3001'
asr_channel = 'asr_channel'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

red = redis.Redis(host='localhost', port=6379, password='')

wasTalking = dict() # This is to send some more data chunks to help kaldi finalize the last utterance
async def socket_to_redis(websocket, path):
    path = parse.unquote(path[1:])
    logger.info('Websocket Connection established')
    logger.info('Connected to: ' + path)
    callerDestinationNumber = path.split('/')[0]
    origCallerIDName = path.split('/')[1]
    voiceUserId = origCallerIDName.split('_')
    voiceUserId = voiceUserId[0] + '_' + voiceUserId[1]
    callerUsername = origCallerIDName.split('-bbbID-')[1]
    if len(origCallerIDName.split('-bbbID-')[1].rsplit('_', 1)) > 1:
        language = origCallerIDName.split('-bbbID-')[1].rsplit('_', 1)[1].capitalize()
        if language.startswith('E'):
            language = 'English'
        else:
            language = 'German'
    else:
        language = 'German'
    audioChannel = parse.quote(callerDestinationNumber + '~' + origCallerIDName) + '~audio'
    controlChannel = parse.quote(callerDestinationNumber + '~' + origCallerIDName) + '~control'
    textChannel = parse.quote(callerDestinationNumber + '~' + origCallerIDName) + '~text'
    redis_message('LOADER_START', callerDestinationNumber, origCallerIDName, callerUsername, language, audioChannel, controlChannel, textChannel)
    wasTalkingChunks = 0 
    async for message in websocket:
        if voiceUserId in isTalking:
            red.publish(audioChannel, message)
            wasTalkingChunks = 200 # this number is a guess. To small and Kaldi doesn't complete the utterance. 
            wasTalking[voiceUserId] = wasTalkingChunks
        if wasTalking.get(voiceUserId):
            red.publish(audioChannel, message)
            wasTalking[voiceUserId] -= 1
        if wasTalking[voiceUserId] == 0:
            wasTalking.pop(voiceUserId)
        print(wasTalking)
        

    logger.info('Connection %s closed' % path)
    redis_message('LOADER_STOP', callerDestinationNumber, origCallerIDName, callerUsername, language, audioChannel, controlChannel, textChannel)


def redis_message(event, callerDestinationNumber, origCallerIDName, callerUsername, language, audioChannel, controlChannel, textChannel):
    message = {
                'Event': event,
                'Caller-Destination-Number': callerDestinationNumber,
                'Caller-Orig-Caller-ID-Name': origCallerIDName,
                'Caller-Username': callerUsername,
                'Language' : language,
                'Audio-Channel': audioChannel,
                'Control-Channel': controlChannel,
                'Text-Channel': textChannel,
              }
    logger.info(message)
    red.publish(asr_channel, json.dumps(message))

def maintain_isTalking(): # The idea is to only send data into the database while the person is talking. This should perform way better with multiple silent persons
    pubsub = red.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe('from-akka-apps-redis-channel')
    global isTalking
    isTalking = set()
    while True:
        message = pubsub.get_message()
        if message:
            message = json.loads(message['data'].decode('UTF-8'))
            core = message.get('core')
            event = core['header']['name']
            if event == 'UserTalkingVoiceEvtMsg':
                if core['body']['talking'] == True:
                    isTalking.add(core['body']['voiceUserId'])
                else:
                    isTalking.discard(core['body']['voiceUserId'])
            # print(talking)
        time.sleep(0.1)

mti = Thread(target=maintain_isTalking)
mti.deamon = True
mti.start()

start_server = websockets.serve(socket_to_redis, 'localhost', port)

asyncio.get_event_loop().run_until_complete(start_server)
logger.info('Websocket Server started on Port ' + port)
asyncio.get_event_loop().run_forever()
