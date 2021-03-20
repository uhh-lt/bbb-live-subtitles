import os
import redis
import json
import multiprocessing as mp
import time
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def start_kaldi(server, input, output, controlChannel, speaker):
    chDir = "/home/6geislin/kaldi-model-server"
    kaldiDir = "kms_env/bin/python3.7 nnet3_model.py -m 0 -e -t -y models/kaldi_tuda_de_nnet3_chain2.yaml --redis-server=%s --redis-audio=%s --redis-channel=%s --redis-control=%s -s='%s' -fpc 190" % (server, input, output, controlChannel, speaker)
    os.chdir(chDir)
    os.system(kaldiDir)


def wait_for_channel(server, port, channel):
    red = redis.Redis(host=server, port=port, password="")
    pubsub = red.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    while True:
        time.sleep(0.2)
        message = pubsub.get_message()
        try:
            if message:
                message = json.loads(message["data"].decode("UTF-8"))
                print(message)
                callerUsername = message["Caller-Username"]
                audioChannel = message["Audio-Channel"]
                textChannel = message["Text-Channel"]
                controlChannel = message["Control-Channel"]
                callerDestinationNumber = message["Caller-Destination-Number"]
                origCallerIDName = message["Caller-Orig-Caller-ID-Name"]
                if message["Event"] == "LOADER_START":
                    print("Start Kaldi")
                    p = mp.Process(target=start_kaldi, args=(server, audioChannel, textChannel, controlChannel, callerUsername))
                    p.start()
                    # kaldiInstances[audioChannel] = p
                    redis_channel_message(red, channel, "KALDI_START", callerDestinationNumber, origCallerIDName, callerUsername, audioChannel, textChannel, controlChannel)
                    
                if message["Event"] == "LOADER_STOP":
                    audioChannel = message["Audio-Channel"]
                    controlChannel = message["Control-Channel"]
                    
                    kaldi_shutdown(red, audioChannel, controlChannel)
                    redis_channel_message(red, channel, "KALDI_STOP", callerDestinationNumber, origCallerIDName, callerUsername, audioChannel, textChannel, controlChannel)
                
        except Exception as e:
            print(e)
            pass


def kaldi_shutdown(red, audioChannel, controlChannel):
    print(controlChannel)
    logger.info("Stop Kaldi")
    red.publish(controlChannel, "shutdown")
    time.sleep(0.5)
    red.publish(audioChannel, 8*"\x00")
    time.sleep(0.5)
    red.publish(audioChannel, 8*"\x00")

def redis_channel_message(red, channel, Event, callerDestinationNumber, origCallerIDName, callerUsername, inputChannel, outputChannel, controlChannel):
    message = {
                "Event": Event,
                "Caller-Destination-Number": callerDestinationNumber,
                "Caller-Orig-Caller-ID-Name": origCallerIDName,
                "Caller-Username": callerUsername,
                "Audio-Channel": inputChannel,
                "Text-Channel": outputChannel,
                "Control-Channel": controlChannel
    }
    red.publish(channel, json.dumps(message))


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-s", "--server", help="REDIS Pubsub Server hostname or IP")
    parser.add_argument("-p", "--port", help="REDIS Pubsub Port", default="6379")
    parser.add_argument("-c", "--channel", help="The Pubsub Information Channel")
    args = parser.parse_args()
    server = args.server
    port = args.port
    channel = args.channel

    wait_for_channel(server, port, channel)
