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

def _webserver(params, currentState = {}):
    # Split matched params on , and spaces
    splittedParams = re.split(r'[,\s]+', params)

    deviceName = splittedParams.pop(0)
    apacheMods = splittedParams

    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)
    currDevice.services.append(WebServer(currDevice, apacheMods))

def _balancer(params, currentState = {}):
    # Split matched params on , and spaces
    splittedParams = re.split(r'[,\s]+', params)

    deviceName = splittedParams.pop(0)
    mode = splittedParams.pop(0)
    sourceInterfaceNum = splittedParams.pop(0)
    destinationDevices = splittedParams

    if mode != "random" and mode != "nth":
        raise Exception("%s mode not supported on Load Balancer." % mode)

    if len(destinationDevices) <= 0:
        raise Exception("You should declare at least one device for Load Balancer %s." % deviceName)

    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)
    currDevice.services.append(LoadBalancer(currDevice, mode, sourceInterfaceNum, destinationDevices))

def _has_name(name, currentState = {}):
    currDevice = currentState["currDevice"]
    currLab = currentState["currLab"]

    currLab.nameserverTree.addNamedDevice(name, currDevice, currentState["currInterface"])

def _ns_resolv(deviceName, nsName2ifaceNum, currentState = {}):
    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)
    nsName, ifaceNum = nsName2ifaceNum.split("|")

    currDevice.services.append(NameserverDefault(currDevice, nsName, ifaceNum))

def _dns(deviceName, name, type, currentState = {}):
    currLab = currentState["currLab"]
    currDevice = currLab.get(deviceName)

    currLab.nameserverTree.addDNSDevice(name, type, currDevice)

    nsService = currDevice.hasService(Nameserver)
    if not nsService:
        nsService = Nameserver(currDevice)
        currDevice.services.append(nsService)

names2commands = {
    "^ip\\((.+)\\)$": _ip,
    "^to\\((.+)\s?,\s?(.+)\\)$": _to,
    "^webserver(?:\\()(.+)+(?:\\))$": _webserver,
    "^balancer(?:\\()(.+)+(?:\\))$": _balancer,
    "^has_name\\((.+)\\)$": _has_name,
    "^ns_resolv\\((.+)\s?,\s?(.+)\\)$": _ns_resolv,
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
    def __init__(self, device, mods):
        self.device = device
        self.mods = mods

    def dump(self, startupFile):
        os.makedirs(self.device.name + "/var/www/html")

        for mod in self.mods:
            startupFile.write("a2enmod %s\n" % mod)

        startupFile.write("/etc/init.d/apache2 start\n")

class LoadBalancer(object):
    def __init__(self, device, mode, sourceInterfaceNum, destinationDevices):
        self.device = device

        self.mode = mode
        self.sourceInterfaceNum = sourceInterfaceNum.replace("eth", "")
        self.destinationDevices = destinationDevices

    def dump(self, startupFile):
        sourceIp = self.device.getInterfaceByNum(self.sourceInterfaceNum).getIp()

        for name2iface in self.destinationDevices:
            name, interfaceNum = name2iface.split("|")
            destIp = self.device.lab.get(name).getInterfaceByNum(interfaceNum.replace("eth", "")).getIp()

            ipTablesParams = "--mode random --probability ##PROB##"
            if self.mode == "nth":
                ipTablesParams = "--mode nth --every ##N##"

            startupFile.write("iptables --table nat --append PREROUTING --destination %s -p tcp --dport ##PORT## --match statistic %s --jump DNAT --to-destination %s:##DESTPORT##\n" % (sourceIp, ipTablesParams, destIp))

class NameserverDefault(object):
    def __init__(self, device, nsName, nsIface):
        self.device = device

        self.nsName = nsName
        self.nsIface = nsIface.replace("eth", "")

    def dump(self, startupFile):
        os.makedirs(self.device.name + "/etc/")

        with open(self.device.name + "/etc/resolv.conf", "w") as resolvFile:
            # Search Name for this NS Device
            name = self.device.lab.nameserverTree.getNameByDevice(self.nsName)
            nsIp = self.device.lab.get(self.nsName).getInterfaceByNum(self.nsIface).getIp()

            # Purge last dot
            if name != None:
                name = name[:-1]

            resolvFile.write("nameserver %s\n" % nsIp)

            if name != None: # If local DNS (or not declared, skip the line)
                resolvFile.write("search %s" % name)

class Nameserver(object):
    def __init__(self, device):
        self.device = device

    def dump(self, startupFile):
        # Write bind startup in startup file
        startupFile.write("/etc/init.d/bind start\n")

        # Prepare bind directory for Namespace dump
        os.makedirs(self.device.name + "/etc/bind")


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

    # Checks if the Device has a specified Service, if so return the first instance. If not, return False.
    def hasService(self, type):
        for service in self.services:
            if isinstance(service, type):
                return service

        return False

class NameserverTree(object):
    def __init__(self):
        self.roots = self._initNode(".")
        self.locals = []

        self.NAMED_STUB = "zone \"%s\" {\n\ttype %s;\n\tfile \"/etc/bind/%s\";\n};\n\n"
        self.DB_STUB = "$TTL   60000\n@               IN      SOA     %s.%s    root.%s.%s 2006031201 28800 14400 3600000 0\n\n"

    def _initNode(self, name):
        return {
            "name": name,               # Name of the zone: ex. lugroma3.org.
            "hostnames2devices": [],    # Devices which aren't involved as nameservers
            "nsDevices2types": [],      # Devices which are part of NS infrastructure, couple (Device instance, NS type (ex. master))
            "servedNames": {}           # Children served names of the current name
        }

    def addDNSDevice(self, name, type, device):
        if name == ".": # This is a root NS, add it to the roots
            self.roots["nsDevices2types"].append((device, type))
            return

        if name == "None": # No name defined
            if type == "local": # Type MUST be local!
                self.locals.append(device)
                return
            else:
                raise Exception("You should declare a name if type isn't `local` @ %s" % device.name)

        # Start tree recursion
        names = name.split('.')
        names.pop()

        self._addToName(self.roots, names, "", type, "nsDevices2types", device)

    def addNamedDevice(self, name, device, iface):
        if name == ".":
            raise Exception("You can't add a named host to the root DNS name!");

        names = name.split('.')
        hostName = names.pop(0) # Gets hostname, example: pc1.lugroma3.org => pc1

        self._addToName(self.roots, names, "", "", "hostnames2devices", (hostName, device, iface))

    def _addToName(self, parentNode, names, name, type, devType, device):
        nextName = names.pop()
        finalName = nextName + "." + name

        # Add Served Name to the current namenode.
        if nextName not in parentNode["servedNames"]:
            parentNode["servedNames"][nextName] = self._initNode(finalName)

        # End of recursion
        if len(names) == 0:
            # Append device to the current name.
            parentNode["servedNames"][nextName][devType].append((device, type))
            return

        self._addToName(parentNode["servedNames"][nextName], names, finalName, type, devType, device)

    def dump(self):
        # Write root info on each device ONLY ONCE
        self._writeRootInfo(self.roots)

        # Dump other names
        self._realDump(None, self.roots)

        # Dump local NS
        self._dumpLocals()

    def _writeRootInfo(self, currentNode):
        # Foreach device declared in the current name.
        for device2type in currentNode["nsDevices2types"]:
            self._writeRootNamedConf(device2type[0], currentNode["name"])

        # Write in devices declared in children.
        for servedNames in currentNode["servedNames"]:
            self._writeRootInfo(currentNode["servedNames"][servedNames])

    def _realDump(self, parentNode, currentNode):
        # Split the name into chunks to perform actions and remove empty strings.
        names = currentNode["name"].split(".")
        names = filter(lambda x: x != "", names)
        isRoot = False

        # We're on root, assign standard name "db.root"
        if len(names) == 0:
            dbFileName = "db.root"
            isRoot = True
        else: # We're not on root, parse db name from name
            plainName = list(names)
            names.reverse() # The db file is written in reverse order
            dbFileName = "db." + ".".join(names)

        # Foreach device declared in the current name.
        for device2type in currentNode["nsDevices2types"]:
            # We're not in root.
            if not isRoot:
                # So we should also write db.root file!
                self._writeDBRootFile(device2type[0])

                # Write Info About Served Names (!= root) in named.conf file
                with open(device2type[0].name + "/etc/bind/named.conf", "a") as namedFile:
                    namedFile.write(self.NAMED_STUB % (".".join(plainName), device2type[1], dbFileName))

            # We shold write db files now with dbName took before.
            with open(device2type[0].name + "/etc/bind/" + dbFileName, "w") as dbFile:
                deviceName = device2type[0].name
                name = currentNode["name"]

                # Special names for root node.
                if isRoot:
                    deviceName = "ROOT-SERVER"
                    name = ""

                # Write DB file header
                dbFile.write(self.DB_STUB % (deviceName, name, deviceName, name))

                # Write info about myself
                dbFile.write("@     IN  NS  %s.%s\n" % (deviceName, name))

                if isRoot:
                    deviceName += "."

                # TODO: By default we pick eth0, that's not ok...
                dbFile.write("%s    IN  A   %s\n\n" % (deviceName, device2type[0].getInterfaceByNum("0").getIp()))

                if len(currentNode["servedNames"]) > 0: # I'm not a leaf, write what I know about my children
                    for servedNames in currentNode["servedNames"]:
                        currentNameInfo = currentNode["servedNames"][servedNames]
                        shortName = currentNameInfo["name"]

                        if not isRoot:
                            # Example: fullName = lugroma3.org. => shortName = lugroma3
                            # Why `not isRoot`? Because in root we want => org. instead of => org!
                            shortName = currentNameInfo["name"].replace(currentNode["name"], "")[:-1]

                        for childrenDevice2type in currentNameInfo["nsDevices2types"]:
                            dbFile.write("%s    IN  NS  %s.%s\n" % (shortName, childrenDevice2type[0].name, currentNameInfo["name"]))
                            # TODO: By default we pick eth0, that's not ok...
                            dbFile.write("%s.%s IN  A   %s\n\n" % (childrenDevice2type[0].name, shortName, childrenDevice2type[0].getInterfaceByNum("0").getIp()))

                if len(currentNode["hostnames2devices"]) > 0: # I have some registered hosts!
                    for hostname2dev2ifaceCouple in currentNode["hostnames2devices"]:
                        # TODO This trick should be purged 4ever.
                        # This is a couple (because we put it in the recursive function _addToName) with (device, type)
                        # Throw away type!
                        hostname2dev2iface = hostname2dev2ifaceCouple[0]
                        dbFile.write("%s IN  A   %s\n" % (hostname2dev2iface[0], hostname2dev2iface[2].getIp()))

        # Foreach served name, do the same stuff.
        for servedNames in currentNode["servedNames"]:
            self._realDump(currentNode, currentNode["servedNames"][servedNames])

    def _dumpLocals(self):
        for device in self.locals:
            self._writeDBRootFile(device)
            self._writeRootNamedConf(device, "")

    def _writeDBRootFile(self, device):
        with open(device.name + "/etc/bind/db.root", "w") as dbRootFile:
            dbRootFile.write(". IN  NS  ROOT-SERVER.\n")
            for rootDevices2types in self.roots["nsDevices2types"]:
                # TODO: By default we pick eth0, that's not ok...
                dbRootFile.write("ROOT-SERVER.  IN  A   %s\n" % rootDevices2types[0].getInterfaceByNum("0").getIp())

    def _writeRootNamedConf(self, device, name):
        with open(device.name + "/etc/bind/named.conf", "a") as namedFile:
            rootType = "hint"

            # We're on root, db.root type is "master" instead of "hint"
            if name == ".":
                rootType = "master"

            namedFile.write(self.NAMED_STUB % (".", rootType, "db.root"))

    def getNameByDevice(self, deviceName):
        return self._getNameByDeviceRecursive(self.roots, deviceName)

    def _getNameByDeviceRecursive(self, currentNode, deviceName):
        # Scan in current DNS devices
        for device2type in currentNode["nsDevices2types"]:
            # If we found the device
            if device2type[0].name == deviceName:
                # Return the name of this node + the previous ones
                return currentNode["name"]

        # No luck, search in children
        for servedNames in currentNode["servedNames"]:
            # Append served name to current full name
            result = self._getNameByDeviceRecursive(currentNode["servedNames"][servedNames], deviceName)
            if result != None:
                return result

        # No luck in children, return None
        return None

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

        self.nameserverTree.dump()

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

    try:
        currLab.dump()
    except Exception as e:
        print "Error %s" % str(e)

parse()
