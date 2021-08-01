from jaspion import Jaspion
from jaspion.utils import filtrate
import redis
import json
import logging
import argparse
from urllib import parse

server = 'YOUR BBB SERVER'
ws_port = '3001'
asr_channel = 'asr_channel'

# TODO: Add parameter to both
app = Jaspion(host='127.0.0.1', port=8021, password='YOUR FREESWITCH PASSWORD')
red = redis.Redis(host=server, port=6379, password='')

logging.basicConfig()
logger = logging.getLogger('ESL-Bridge')
logger.setLevel(logging.DEBUG)


@app.handle('conference::maintenance')
@filtrate('Action', 'add-member')
def add_member(event):
    logger.info('add-member')
    # logger.debug(event)
    uuid = event['Unique-ID']
    Event = 'add-member'
    callerDestinationNumber = event['Caller-Destination-Number'].replace('echo', '')
    callerOrigCallerIdName = event['Caller-Orig-Caller-ID-Name']
    language = event['Caller-Orig-Caller-ID-Name'].rsplit('_', 1)[1].capitalize()
    callerId = callerOrigCallerIdName.partition('-bbbID-')[0]
    callerUsername = callerOrigCallerIdName.partition('-bbbID-')[2]
    socket_adress = 'ws://' + server + ':' + ws_port + '/' + \
                    callerDestinationNumber + '/' + \
                    parse.quote(callerOrigCallerIdName)
    app.command(command='uuid_audio_fork ' + uuid + ' start ' + socket_adress + ' mono 16k', background=False)
    if language.startswith('E'):
        language = 'English'
    else:
        language = 'German'

    add_member = {
                  'Event': Event,
                  'Caller-Destination-Number': callerDestinationNumber,
                  'Caller-Orig-Caller-ID-Name': callerOrigCallerIdName,
                  'Caller-ID': callerId,
                  'Caller-Username': callerUsername,
                  'UUID': uuid,
                  'Language': language
                 }
    send_to_pubsub(add_member)


@app.handle('mod_audio_fork::connect')
def mod_audio_fork_connect(event):
    logger.info('mod_audio_fork::connect')
    # logger.debug(event)
    # uuid = event['Unique-ID']
    Event = 'mod_audio_fork::connect'
    callerDestinationNumber = event['Caller-Destination-Number'].replace('echo', '')
    origCallerIDName = event['Caller-Orig-Caller-ID-Name']
    callerUsername = origCallerIDName.partition('-bbbID-')[2]

    maf_connect = {
                    'Event': Event,
                    'Caller-Destination-Number': callerDestinationNumber,
                    'Caller-Orig-Caller-ID-Name': origCallerIDName,
                    'Caller-Username': callerUsername,
                  }
    send_to_pubsub(maf_connect)


@app.handle('conference::maintenance')  # TODO
@filtrate('Action', 'del-member')
def del_member(event):
    print(event)


# TODO:Add Heartbeat to check if the connection is lost

def send_to_pubsub(data):
    logger.debug('Redis Message to ' + asr_channel + ' :')
    logger.debug(data)
    data = json.dumps(data)
    red.publish(asr_channel, data)


if __name__ == '__main__':
    # Argument Parser
    # parser = argparse.ArgumentParser()

    # # flag (- and --) arguments
    # parser.add_argument('-s', '--server', help='REDIS Pubsub Server hostname or IP')
    # parser.add_argument('-c', '--channel', help='The Pubsub Information Channel')
    # parser.add_argument('-fs', '--freeswitchServer', help='Freeswitch Server hostname or IP')
    # parser.add_argument('-fp', '--freeswitchPassword', help='Freeswitch Password')

    app.run()
