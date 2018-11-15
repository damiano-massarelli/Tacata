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
        raise Exception("Invalid ip %s." % address)

    for item in parts:
        if (not 1 <= len(item) <= 3) or (not 0 <= int(item) <= 255):
            raise Exception("Invalid ip %s." % address)

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
    currDevice.services.append(WebServer(currDevice))

def _balancer(params, currentState = {}):
    # Split matched params on , and spaces
    splittedParams = re.split(r'[,\s]+', params)

    deviceName = splittedParams.pop(0)
    mode = splittedParams.pop(0)
    sourceInterfaceNum = splittedParams.pop(0)
    destinationDevices = splittedParams

    if mode != "random":
        raise Exception("%s mode not supported on Load Balancer." % mode)

    if len(destinationDevices) <= 0:
        raise Exception("You should declare at least one device for Load Balancer %s." % deviceName)

    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)
    currDevice.services.append(LoadBalancer(currDevice, sourceInterfaceNum, destinationDevices))

def _ns(localNsIp, currentState = {}):
    isValidIP(localNsIp)

    currDevice = currentState["currDevice"]
    currDevice.services.append(NameserverDefault(currDevice, localNsIp))

def _dns(deviceName, name):
    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)

    currLab.nameserverTree.addNamedDevice(name, currDevice)

    print currLab.nameserverTree



names2commands = {
    "^ip\\((.+)\\)$": _ip,
    "^to\\((.+)\s?,\s?(.+)\\)$": _to,
    "^webserver\\((.+)\\)$": _webserver,
    "^balancer(?:\\()(.+)+(?:\\))$": _balancer,
    "^ns\\((.+)\\)$": _ns,
    "^dns\\((.+)\s?,\s?(.+),\s?(.+)\\)$": _dns
}

##############
## SERVICES ##
##############
class Interface(object):
    def __init__(self, device, index):
        self.device = device

        self.index = index
        self.ip = None
        self.gateways = []

    def setIp(self, ip):
        isValidIP(ip)
        self.ip = ip

    def getIp(self, withSubnet = False):
        if withSubnet:
            return self.ip

        return self.ip.split("/")[0]

    def dump(self, startupFile):
        dumpString = "ifconfig eth%s %s up\n" % (self.index, self.ip)
        for gateway in self.gateways:
            netLine = "default"

            if gateway[0] != DEFAULT_GW_STRING:
                netLine = "-net %s" % (gateway[0])

            dumpString += "route add %s gw %s dev eth%s\n" % (netLine, gateway[1], self.index)

        startupFile.write(dumpString)

class WebServer(object):
    def __init__(self, device):
        self.device = device

    def dump(self, startupFile):
        os.makedirs(self.device.name + "/var/www/html")
        startupFile.write("/etc/init.d/apache2 start")

class LoadBalancer(object):
    def __init__(self, device, sourceInterfaceNum, destinationDevices):
        self.device = device

        self.sourceInterfaceNum = sourceInterfaceNum.replace("eth", "")
        self.destinationDevices = destinationDevices

    def dump(self, startupFile):
        sourceIp = self.device.getInterfaceByNum(self.sourceInterfaceNum).getIp()

        for name2iface in self.destinationDevices:
            name, interfaceNum = name2iface.split("|")
            destIp = self.device.lab.get(name).getInterfaceByNum(interfaceNum.replace("eth", "")).getIp()

            startupFile.write("iptables --table nat --append PREROUTING --destination %s -p tcp --dport ##PORT## --match statistic --mode random --probability ##PROB## --jump DNAT --to-destination %s:##DESTPORT##\n" % (sourceIp, destIp))

class NameserverDefault(object):
    def __init__(self, device, nsIp):
        self.device = device

        self.nsIp = nsIp

    def dump(self, startupFile):
        with open(self.device.name + "/etc/resolv.conf", "w") as resolvFile:
            resolvFile.write("nameserver %s" % self.nsIp)


#####################
## GENERIC CLASSES ##
#####################
class Device(object):
    def __init__(self, lab, name):
        self.lab = lab
        self.name = name
        self.services = []

    def dump(self):
        os.mkdir(self.name)
        with open(self.name + ".startup", "w") as deviceFile:
            for service in self.services:
                service.dump(deviceFile)

    def getInterfaceByNum(self, index):
        for service in self.services:
            if isinstance(service, Interface) and index == service.index:
                return service

        raise Exception("Interface %s not found on device %s." % (index, self.name))

class NameserverTree(object):
    def __init__(self):
        self.roots = self._initNode(".")

    def _initNode(self, name):
        return {
            "name": name,
            "devices": [],
            "servedNames": []
        }

    def addNamedDevice(self, name, device):
        if name == ".": # This is a root NS, add it to the roots
            self.roots.devices.append(device)
            return

        # Start tree recursion
        names = name.split('.')
        names.pop()

        self._addToName(self.roots, names, device)

    def _addToName(self, parentNode, names, device):
        nextName = names.pop()
        if nextName not in parentNode.servedNames:
            parentNode.servedNames[nextName] = self._initNode(names)

        if len(names) == 1: # End of recursion
            parentNode.servedNames[nextName].devices.append(device)
            return

        self._addToName(parentNode.servedNames[nextName], nextName, device)


class Lab(object):
    def __init__(self):
        # configuration for netkit lab.conf
        self.confLines = []
        self.name2devices = {}
        self.nameserverTree = NameserverTree()
        self.labDir = "lab"

        if os.path.exists(self.labDir):
            wantDelete = raw_input("A lab already exists, do you want to overwrite it [y/n]? ")
            if wantDelete == "y":
                shutil.rmtree(self.labDir, ignore_errors = True)

        os.mkdir(self.labDir)
        os.chdir(self.labDir)

    def addConfLine(self, line):
        self.confLines.append(line)

    def getOrNew(self, name):
        if name not in self.name2devices:
            self.name2devices[name] = Device(self, name)

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
    matches = re.search("(.*)\\[(\d+)\\]=\"?(\w)\"?", declaration)
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
                line = line.replace("\n", "").replace("\r", "").strip()
                if line == "" or line.startswith("#"): # Skip empty lines and comments
                    continue

                netkitDef, commands = line.split("$")
                netkitDef = netkitDef.strip()

                currDevice, currInterface = None, None

                if netkitDef != "":
                    currLab.addConfLine(netkitDef)

                    currDeviceName, currInterfaceNum = parseDeviceAndInterface(netkitDef)

                    currDevice = currLab.getOrNew(currDeviceName)
                    currInterface = Interface(currDevice, currInterfaceNum)
                    currDevice.services.append(currInterface)

                parseCommands(commands, currDevice = currDevice, currInterface = currInterface, currLab = currLab)
            except Exception as e:
                print "Error at line %d: %s" % (currentLine, str(e))
                return

            currentLine += 1

        currLab.dump()

parse()