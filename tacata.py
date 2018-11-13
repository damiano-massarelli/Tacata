import os 
import re
import shutil

###############
## CONSTANTS ##
###############
DEFAULT_GW_STRING = "default"

def isValidIP(address):
    parts = address.split('/')[0].split(".")
    
    if len(parts) != 4:
        raise Exception("Invalid ip %s" % address)
    
    for item in parts:
        if (not 1 <= len(item) <= 3) or (not 0 <= int(item) <= 255):
            raise Exception("Invalid ip %s" % address)

##############
## COMMANDS ##
##############
def _ip(addr, currentState = {}):
    currInterface = currentState["currInterface"]
    currInterface.setIp(addr)

def _to(destination, gw, currentState = {}):
    if destination != DEFAULT_GW_STRING:
        isValidIP(destination)
    
    isValidIP(gw)

    currInterface = currentState["currInterface"]
    currInterface.gateways.append((destination, gw))

def _webserver(deviceName, currentState = {}):
    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)
    currDevice.services.append(WebServer(deviceName))


names2commands = {
    "^ip\\((.+)\\)$": _ip,
    "^to\\((.+)\s?,\s?(.+)\\)$": _to,
    "^webserver\\((.+)\\)$": _webserver
}

class Interface(object):
    def __init__(self, index):
        self.index = index
        self.ip = None
        self.gateways = []

    def setIp(self, ip):
        isValidIP(ip)
        self.ip = ip
    
    def dump(self, startupFile):
        dumpString = "ifconfig eth%s %s up\n" % (self.index, self.ip)
        for gateway in self.gateways:
            netLine = "default"

            if gateway[0] != DEFAULT_GW_STRING:
                netLine = "-net %s" % (gateway[0])
            
            dumpString += "route add %s gw %s dev eth%s\n" % (netLine, gateway[1], self.index)

        startupFile.write(dumpString)

class WebServer(object):
    def __init__(self, deviceName):
        self.deviceName = deviceName

    def dump(self, startupFile):
        os.makedirs(self.deviceName + "/var/www/html")
        startupFile.write("/etc/init.d/apache2 start")
        
class Device(object):
    def __init__(self, name):
        self.name = name
        self.services = []

    def dump(self):
        os.mkdir(self.name)
        with open(self.name + ".startup", "w") as deviceFile:
            for service in self.services:
                service.dump(deviceFile)

class Lab(object):
    def __init__(self):
        # configuration for netkit lab.conf
        self.confLines = []
        self.name2devices = {}
        self.labDir = "lab"

        if os.path.exists(self.labDir):
            wantDelete = raw_input("A lab already exists, do you want to overwrite it? [y/n]")
            if wantDelete == "y":
                shutil.rmtree(self.labDir, ignore_errors = True)

        os.mkdir(self.labDir)
        os.chdir(self.labDir)

    def addConfLine(self, line):
        self.confLines.append(line)

    def getOrNew(self, name):
        if name not in self.name2devices:
            self.name2devices[name] = Device(name)

        return self.name2devices[name]

    def get(self, name):
        return self.name2devices[name]

    def dump(self):
        confString = "\n".join(self.confLines)
        with open("lab.conf", "w") as labConfFile:
            labConfFile.write(confString)

        for device in self.name2devices:
            self.name2devices[device].dump()

def parseDeviceAndInterface(declaration):
    if declaration == "":
        return None, None
    matches = re.search("(.*)\\[(\d+)\\]=(\w)", declaration)
    return matches.group(1), matches.group(2)

def parseCommands(commandString, **kwargs):
    commands = commandString.split(";")
    commands = [command.strip() for command in commands if command.strip() != ""] # trim em all
    for command in commands:
        commandFound = False

        for commandRe in names2commands:
            matches = re.search(commandRe, command)
            if matches is not None:
                args = matches.groups()
                names2commands[commandRe](*args, currentState=kwargs)
                commandFound = True
                break
        if not commandFound:
            raise Exception("Command '%s' not declared!" % command)

def parse():
    currLab = Lab()
    with open("../lab.confu", "r") as labfile:
        currentLine = 1
        for line in labfile:
            try:
                line = line.replace("\n", "").replace("\r", "")
                netkitDef, commands = line.split("$")
                netkitDef = netkitDef.strip()

                currDevice, currInterface = None, None

                if netkitDef != "":
                    currLab.addConfLine(netkitDef)

                    currDeviceName, currInterfaceNum = parseDeviceAndInterface(netkitDef)

                    currDevice = currLab.getOrNew(currDeviceName)
                    currInterface = Interface(currInterfaceNum)
                    currDevice.services.append(currInterface)

                parseCommands(commands, currDevice = currDevice, currInterface = currInterface, currLab = currLab)
            except Exception as e:
                print "Error at line %d: %s" % (currentLine, str(e))
                return

            currentLine += 1

        currLab.dump()

parse()