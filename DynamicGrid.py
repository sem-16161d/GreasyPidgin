import math

class DynamicGrid:
        def __init__(self, dynamicStepdB=-3, headroomdB = -1,possibleDynamicsString = None):
            if possibleDynamicsString is None:
                possibleDynamicsString = ['ppppp','pppp','ppp','pp','p','mp','mf','f','ff','fff','ffff','fffff']
            self.dynamicStepdB = dynamicStepdB
            self.possibleDynamicsString = possibleDynamicsString
            self.possibleDynamicsdB = [i * self.dynamicStepdB +headroomdB for i in reversed(range(len(self.possibleDynamicsString )))]
            self.dynamicMapping = list(zip(self.possibleDynamicsString,self.possibleDynamicsdB))
        
        def quantizedB(self,dB = -12.34567):
            return min(self.possibleDynamicsdB, key=lambda x: abs(x - dB))
        
        def mapdBToDynamic(self, dB = -12.34567):
            dB = self.quantizedB(dB)
            return self.possibleDynamicsString[self.possibleDynamicsdB.index(dB)]