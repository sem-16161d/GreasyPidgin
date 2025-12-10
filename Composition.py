################################################################################
################################################################################
import math
import numpy as np
from .DynamicGrid import DynamicGrid
from .TimeGrid import TimeGrid
from .PitchGrid import PitchGrid
from musicscore.chord import Chord
from .Instrument import Instrument
from .Player import Player
from .Event import Event
################################################################################
################################################################################
class Composition:
    def __init__(
        self,
        durationSec=10, bpm=120, possibleBeatSubdivision=None,
        meter=(4, 4),
        refFreq=443.0, refMidi=69, stepsPerOctave=12, midiMin=0, midiMax=130,
        dynamicStepdB=-3, headroomdB=-1, possibleDynamicsString=None,

        playerList = None
    ):
        if playerList is None:
            print("Warning: No Players in List!")
            self.playerList = []
        else:
            self.playerList = playerList

        if possibleBeatSubdivision is None:
            possibleBeatSubdivision = [4]

        self.durationSec = durationSec
        self.bpm = bpm
        self.possibleBeatSubdivision = possibleBeatSubdivision
        self.meter = meter

        self.refFreq = refFreq
        self.refMidi = refMidi
        self.stepsPerOctave = stepsPerOctave
        self.midiMin = midiMin
        self.midiMax = midiMax

        self.dynamicStepdB = dynamicStepdB
        self.headroomdB = headroomdB

        if possibleDynamicsString is None:
            possibleDynamicsString = [
                'ppppp','pppp','ppp','pp','p','mp',
                'mf','f','ff','fff','ffff','fffff'
            ]
        self.possibleDynamicsString = possibleDynamicsString

        self.dynamicGrid = DynamicGrid(
            self.dynamicStepdB,
            self.headroomdB,
            self.possibleDynamicsString
        )

        self.timeGrid = TimeGrid(
            self.durationSec,
            self.bpm,
            self.possibleBeatSubdivision
        )

        self.pitchGrid = PitchGrid(
            stepsPerOctave=self.stepsPerOctave,
            refFreq=self.refFreq,
            refMidi=self.refMidi,
            midiMin=self.midiMin,
            midiMax=self.midiMax
        )

        self.totalEventList = []

    def quantizeEventToBeats(self, ev=None):
        if ev is None:
            print("No event")
            return

        beatDur = self.timeGrid.beatDurationSec
        startBeatRaw = ev.startTimeSec / beatDur
        endBeatRaw   = (ev.startTimeSec + ev.durationSec) / beatDur
        qStart = self.timeGrid.quantizeBeat(startBeatRaw)
        qEnd   = self.timeGrid.quantizeBeat(endBeatRaw)

        durBeats = max(qEnd - qStart, 0.0)

        ev.startTimeBeats = qStart
        ev.endTimeBeats   = qEnd
        ev.quarterDurationFloat = durBeats 

        ev.startTimeSec = qStart * beatDur
        ev.durationSec  = durBeats * beatDur
        ev.endTimeSec   = ev.startTimeSec + ev.durationSec

        if [m.value for m in ev.chord.midis] != [0]:
            ev.chord.quarter_duration = durBeats
            
    def quantizeEventListToBeats(self,playerIndex = 0):
        player = self.playerList[playerIndex]
        player.sortEventsByTime()
        evList = player.eventList
        for ev in evList:
            self.quantizeEventToBeats(ev)

    def removeEmptyEvents(self, playerIndex=0):
        player = self.playerList[playerIndex]
        evList = player.eventList
        minDur = self.timeGrid.fastestDivisionTime
        player.eventList = [
            ev for ev in evList
            if not (
                ev.quarterDurationFloat < minDur and
                [m.value for m in ev.chord.midis] == [0]   # rest check
            )
        ]
        player.updateTimesSec()

    def removeGraceNotes(self, playerIndex=0, tol=1e-9):
        player = self.playerList[playerIndex]
        evList = player.eventList
        player.eventList = [
            ev for ev in evList
            if abs(ev.chord.quarter_duration) > tol
        ]
        player.updateTimesSec()

    def removeSimultaneousEvents(self, playerIndex=0):
        player = self.playerList[playerIndex]
        evList = player.eventList
        startTimes = set()
        kept = []

        for ev in evList:
            startTimeMs = int(ev.startTimeSec * 1000)
            if startTimeMs in startTimes:
                # drop this one
                continue
            startTimes.add(startTimeMs)
            kept.append(ev)

        player.eventList = kept
        player.updateTimesSec()

    def consolidateMinNoteDurationByPlayer(self,playerIndex = 0):
        shortestMicroTime = self.timeGrid.fastestDivisionTime
        player = self.playerList[playerIndex]
        if player.minNoteDurationSec < shortestMicroTime:
            player.minNoteDurationSec = shortestMicroTime
    
    def consolidateDurations(self, playerIndex=0, allowPolyphony=False):
        """cut notes to length or add a pause"""
        player = self.playerList[playerIndex]
        self.consolidateMinNoteDurationByPlayer(playerIndex)
        eventList = player.eventList
        if len(eventList) == 0:
            raise ValueError("consolidateDurations: Player.EventList is empty")
        if allowPolyphony:
            raise ValueError("consolidateDurations: Possibility of Overlapping not yet implemented!")
        player.updateTimesSec()
        for sT, eT, ev in zip(
            player.startTimesSec[1:],
            player.endTimesSec[:-1],
            player.eventList
        ):
            if ev.durationSec < player.minNoteDurationSec:
                player.eventList.remove(ev)
                return
            else:
                differenceSec = sT - eT
                if differenceSec <= player.minRestDurationSec:
                    # cut the event to match the gap
                    ev.durationSec += differenceSec
                    ev.endTimeSec = eT + ev.durationSec
                    ev.quarterDurationFloat = round(ev.durationSec * self.bpm / 60, 3)
                    ev.endTimeBeats = round(ev.endTimeSec * self.bpm / 60, 3)
                    # only update quarter_duration for NON-rests
                    if [m.value for m in ev.chord.midis] != [0]:
                        ev.chord.quarter_duration = ev.quarterDurationFloat
                else:
                    # add a rest
                    player.eventList.append(
                        Event(eT, differenceSec, -100, 0, bpm=self.bpm)
                    )

        player.updateTimesSec()

    

    def consolidateTiedNotes(self):
        for p in self.playerList:
            p.updateTimesSec()
            evList = p.eventList
            for ev in evList:
                startBeats = ev.startTimeBeats
                nextBeat = math.ceil(startBeats)
                diff2NextBeat = nextBeat-startBeats
                durBeats = ev.quarterDurationFloat
                if durBeats > diff2NextBeat:
                    print("in need of a tie!")




        

            


