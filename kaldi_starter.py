import os
import redis
import json
import multiprocessing as mp
import time
import argparse


def start_kaldi(input, output, speaker):
    os.chdir("/home/bbb/ba/kaldi_modelserver_bbb")
    os.system("pykaldi_bbb_env/bin/python3.7 nnet3_model.py -m 0 -e -t -y models/kaldi_tuda_de_nnet3_chain2.yaml --redis-audio=%s --redis-channel=%s -s='%s' -fpc 190" % (input, output, speaker))


def wait_for_channel(server, channel):
    kaldiInstances = {}
    red = redis.Redis(host=server, port=6379, password="")
    pubsub = red.pubsub()
    pubsub.subscribe(channel)

    while True:
        time.sleep(0.2)
        message = pubsub.get_message()
        if message and message["data"] != 1:
            message = json.loads(message["data"].decode("UTF-8"))
            try:
                meetingId = message["meetingId"]
                callerUsername = message["Caller-Username"]
                inputChannel = meetingId + "%" + callerUsername.replace(" ", ".") + "%asr"
                outputChannel = meetingId + "%" + callerUsername.replace(" ", ".") + "%data"
                callerDestinationNumber = message["Caller-Destination-Number"]
                origCallerIDName = message["Caller-Orig-Caller-ID-Name"]
                if message["Event"] == "LOADER_START":
                    print("Start Kaldi")
                    p = mp.Process(target=start_kaldi, args=(inputChannel, outputChannel, callerUsername))
                    p.start()
                    kaldiInstances[inputChannel] = p

                    Loader_Start_msg = {
                                        "Event": "KALDI_START",
                                        "Caller-Destination-Number": callerDestinationNumber,
                                        "meetingId": meetingId,
                                        "Caller-Orig-Caller-ID-Name": origCallerIDName,
                                        "Caller-Username": callerUsername,
                                        "Input-Channel": inputChannel,
                                        "ASR-Channel": outputChannel
                                        }
                    red.publish(channel, json.dumps(Loader_Start_msg))

                if message["Event"] == "LOADER_STOP":
                    inputChannel = message["ASR-Channel"]
                    print("Stop Kaldi")
                    p = kaldiInstances.pop(inputChannel, None)
                    if p:
                        p.terminate()  # TODO: Problems with orphaned processes. Eventually call Kaldi as a module and not with the system
                        p.join()
                        Loader_Stop_msg = {
                                           "Event": "KALDI_STOP",
                                           "Caller-Destination-Number": callerDestinationNumber,
                                           "meetingId": meetingId,
                                           "Caller-Orig-Caller-ID-Name": origCallerIDName,
                                           'Caller-Username': callerUsername,
                                           "Input-Channel": inputChannel,
                                           "ASR-Channel": outputChannel
                                           }
                        red.publish(channel, json.dumps(Loader_Stop_msg))
            except:
                pass


if __name__ == "__main__":
    # Argument parser
    parser = argparse.ArgumentParser()

    # flag (- and --) arguments
    parser.add_argument("-s", "--server", help="REDIS Pubsub Server hostname or IP")
    parser.add_argument("-c", "--channel", help="The Pubsub Information Channel")
    args = parser.parse_args()
    server = args.server
    channel = args.channel

    wait_for_channel(server)
