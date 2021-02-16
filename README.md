# bbb-live-subtitles
This project is a plugin for automatic subtitling in Big Blue Button (BBB), an open source web conferencing system. bbb-live-subtitles will run real time automatic speech recognition (ASR) and will generate subtitle captions on-the-fly. No cloud services are used for ASR, instead we use our own speech recognition models that can be run locally. This ensures that no privacy issues arise.

# Subtitling of BBB Participants
Currently, each BBB participant is subtitled individually. We use Kaldi/pyKaldi for automatic speech recognition (ASR). Any nnet3 compatible Kaldi model can be used. We offer free and ready to use models for [German ASR](https://github.com/uhh-lt/kaldi-tuda-de/) and we are working on making an English model available as well.

# Installation and prerequisites:
Requirements:
Works with BigBlueButton 2.2.x, Ubuntu 16.04 and Python 3.7 and [kaldi-model-server](https://github.com/uhh-lt/kaldi-model-server)

When working with different machines (see Section "usage") the configuration of the redis server must be changed to allow remote access, as outlined below.

## Install Redis and configure it to Accept Remote Connections

On most debian/ubuntu systems you can install redis with:

```Shell
sudo apt install redis-server
```

If you like to host the speech recognition on another server in your local network, you need to allow connections to redis in your local network.
To do that change the configuration file
```Shell
sudo nano /etc/redis/redis.conf
```
change the line `bind 127.0.0.1` and add the IP Adress of the server(eg. 192.168.0.1): `bind 127.0.0.1 192.168.0.1`.
Save the file and restart the redis server
```Shell
sudo /etc/init.d/redis-server restart
```
This would bind redis to the local LAN ip 192.168.0.1 as well as localhost 127.0.0.1. You can now test the access from another machine within your network with `redis-cli` for example:
```Shell
redis-cli -h 192.168.0.1 -p 6379
```
Note that you shouldn't let Redis listen on a public IP, as you would otherwise expose raw speech data packages to the public. If in doubt consult your admin about network and firewall settings and make sure that Redis can only be accessed from trusted hosts.

## Change FreeSWITCH Dialplans
Bbb-live-subtitles interactes directly with FreeSWITCH, the main Voip component that routes the speech data of the participants in BB. In order to add the functunality to record every participant so that bbb-live-subtitles can access the speech data, the FreeSWITCH Dialplan needs to be changed:
Open the `bbb_echo_to_conference.xml` Diaplan and add some lines:
```Shell
sudo nano /opt/freeswitch/etc/freeswitch/dialplan/default/bbb_echo_to_conference.xml
```
Add the following lines above the line `jitterbuffer`:
```XML
      <action application="set" data="RECORD_READ_ONLY=true"/>
      <action application="set" data="record_sample_rate=8000"/> <!-- The samplerate is doubled by FS. Perhaps a bug -->
      <action application="record_session" data="/var/freeswitch/meetings/${strftime(%Y-%m-%d-%H-%M-%S)}_${call_uuid}.wav"/>
```
Save the file and restart FreeSWITCH:
```Shell
sudo service freeswitch restart
```

## Clone and Install
At first create a directory and clone the projects into it:
```Shell
mkdir ~/projects
cd ~/projects
git clone https://www.github.com/uhh-lt/bbb-live-subtitles
```
Create kaldi-model-server and follow the [instructions](https://github.com/uhh-lt/kaldi-model-server#installation)

After these steps create a python virtual environment and start it
```Shell
cd ~/projects/bbb-live-subtitles
virtualenv -p python3 bbb_env
source bbb_env/bin/activate
```
Install the dependencies
```Shell
pip3 install redis jaspion pymongo
```

# Usage
To use this project you can run every script on remote machines or if your machine is fast enough all services on the same machine.
All the scripts need to run before the participant joins the conference. ASR processing is only loaded once it is needed, otherwise the script stand by and wait for participants to join conferences.

At first you need to start `esl_to_redis.py`. This module creates a connection to the FreeSWITCH Software through [ESL](https://freeswitch.org/confluence/display/FREESWITCH/Event+Socket+Library) and writes every information about the media bugs into the information redis channel.

The next to start is `check_redis_and_start_upload.py`. This module checks the redis information channel for started bugs and starts the file upload onto the asr channel. When started on another machine the folder with the recordings must be shared. 

The `kaldi_starter.py` module is in this configuration on another machine (could also run on the same machine) and starts for each media bug a seperate Kaldi instance with the Kaldi-model-server. The kaldi-model-server then sends the transcrived speech back into a separate redis channel. 

With the `mongodbconnector.py` module the ASR Data is written into the mongodb database. To see subtitles, the presenter needs to start the subtitle functionanilty in BBB and then the participants can activate the subtitles by clicking on the CC button.
