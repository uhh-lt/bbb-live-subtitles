import time
from collections import OrderedDict
import threading


class subtitles:

    def __init__(self, meetingId):
        self.meetingId = meetingId
        self.subtitles = OrderedDict()
        self.completeSubtitles = []
        self.lastPointSubtitles = 0

        maintenance = threading.Thread(target=self.__subtitleMaintenance__, args=())
        maintenance.daemon = True
        maintenance.start()

    def __subtitleMaintenance__(self):
        durationSubtitle = 0
        while True:
            subtitles = self.subtitles
            actualTime = time.time()
            new_subtitles = OrderedDict()
            for key, value in subtitles.items():
                if actualTime - value["time"] < durationSubtitle:
                    new_subtitles[key] = value
            self.subtitles = new_subtitles
            time.sleep(1)

    def __utteranceToSubtitle__(self, utterance):
        subtitle = utterance.replace("<UNK>", "").replace("wow", "").replace("ähm", "").replace("äh", "")  # removes hesitations and <UNK> Token
        subtitle = " ".join(subtitle.split())  # removes multiples spaces
        return subtitle

    def __createFullSubtitle__(self, one, two=None):
        if two is not None:
            return one["callerName"] + ": " + one["subtitle"] + "\n" + two["callerName"] + ": " + two["subtitle"]
        else:
            return one["callerName"] + ": " + one["subtitle"] + "\n"

    def insert(self, userId, callerName, utterance, event, priority=0):
        actualTime = time.time()
        subtitles = self.subtitles
        subtitle = self.__utteranceToSubtitle__(utterance)
        if len(subtitle) > 1:
            subtitles[userId] = {
                              "callerName": callerName,
                              "subtitle": subtitle,
                              "time": actualTime,
                              "priority": priority
                            }
            if event == "completeUtterance":
                self.completeSubtitles.append(callerName + ": " + subtitle )
        return subtitles

    def show(self):
        subtitles = self.subtitles
        iterSubtitle = iter(subtitles)
        if len(subtitles) > 0:
            # if len(subtitles) == 1: # When both participants talk at the same time BBB doesnt replace the subtitle it adds another one below it.
            keySub = next(iterSubtitle)
            sub = subtitles[keySub]
            return self.__createFullSubtitle__(sub)
            # else:
            #     keySub1 = next(iterSubtitle)
            #     sub1 = subtitles[keySub1]
            #     keySub2 = next(iterSubtitle)
            #     sub2 = subtitles[keySub2]
            #     return self.__createFullSubtitle__(sub1, sub2)
        else:
            return None

    def list(self):
        print(self.subtitles)

    def latest(self):
        """returns the latest completed subtitles else None"""
        lastPointSubtitles = self.lastPointSubtitles
        
        if len(self.completeSubtitles) is not lastPointSubtitles:
            result = self.completeSubtitles[lastPointSubtitles:]
            self.lastPointSubtitles = len(self.completeSubtitles)

            return result
        else:
            return None


if __name__ == "__main__":
    st = subtitles(123)
    st.insert(456, "John Doe", "Franz jagt im <UNK> Taxi quer       ähm durch wow äh Bayern    ", "partialUtterance")
    time.sleep(1)
    st.list()
    st.insert(111, "Johanna Doe", "Franziska jagt   im völlig verwahrlosten <UNK> quer durch ähhh München", "completeUtterance", 0)
    time.sleep(1)
    st.insert(777, "Alice", "Ferdi Fuchs", 0)
    time.sleep(1)
    # st.insert(456, "Bob", "Frederike Fuchs")
    st.list()
    print(st.show())
