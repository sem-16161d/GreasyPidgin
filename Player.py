from .Instrument import Instrument
from .Event import Event
################################################################################
################################################################################
class Player:
    def __init__(self,
            name = 'player1',
            instrument = Instrument(),
            minNoteDurationSec = 1/12,
            maxNoteDurationSec = 20,
            minRestDurationSec = 1/12,
            bpm = 120
    ):
        self.name = name
        self.instrument = instrument
        self.bpm = bpm
        """initialize the event list with 1 min of silence"""
        self.eventList = [Event(0,60,-100,0,bpm = bpm)]
        self.startTimesSec = []
        self.durationsSec = []
        self.endTimesSec = []
        self.minNoteDurationSec = minNoteDurationSec
        self.maxNoteDurationSec = maxNoteDurationSec
        self.minRestDurationSec= minRestDurationSec

    def addEvent(self,startTimeSec = 0, durationSec = 1.5,
                 dynamicdB = -14, pitchesMidi = 60,bpm = 60):
        self.eventList.append(
            Event(startTimeSec=startTimeSec, durationSec=durationSec,
                  dynamicdB=dynamicdB, pitchesMidi=pitchesMidi, bpm = bpm)
        )

    def sortEventsByTime(self):
        self.eventList = sorted(self.eventList, key=lambda e: e.startTimeSec)

    def updateTimesSec(self):
        self.sortEventsByTime()
        self.startTimesSec = [ev.startTimeSec for ev in self.eventList]
        self.durationsSec = [ev.durationSec for ev in self.eventList]
        self.endTimesSec = [ev.endTimeSec for ev in self.eventList]

    
    def dump(self):
        print(f"""
            name: {self.name}
            instrument(s): {self.instrument.name}
            events:""")
        for ev in self.eventList:
            ev.dump()
################################################################################        
################################################################################