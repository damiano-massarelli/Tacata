# basic_lab
import os

# CONSTS
IFCONFIG_COMMAND = "ifconfig eth%s %s up\n"

DEFAULT_COMMAND = "route add default gw %s dev eth%s\n"

ROUTE_COMMAND = "route add -net %s gw %s dev eth%s\n"

# - BIND
BIND_START = "/etc/init.d/bind start"

NAMED_ROOT_ONLY = """zone "." {
   type %s;
   file "/etc/bind/db.root";
};
"""

NAMED_AUTH = NAMED_ROOT_ONLY + """zone "%s" {
   type master;
   file "/etc/bind/db.%s";
};
"""

# - ZEBRA

ZEBRA_START = "/etc/init.d/zebra start"

RIP_FILE = """hostname ripd
password zebra
enable password zebra

router rip

network %s"""

OSPF_FILE = """hostname ospfd
password zebra
enable password zebra

router ospf

network %s area %s"""

BGP_FILE = """hostname bgpd
password zebra
enable password zebra

router bgp %s
"""

# GLOBAL_VARIABLES
hosts = {}

CONN = "conn"
BGP = "bgp"
RIP = "rip"
OSPF = "ospf"

# CALLABLE FUNCTIONS FROM .CONFU FILE
def rip(hostName, network = "***lan***", *red):
    host = hosts[hostName]
    service = RipService(network, CONN in red, BGP in red, OSPF in red)
    host.addService(service)
    
def bgp(hostName, ASnumber = "***AS number***"):
    host = hosts[hostName]
    service = BgpService(ASnumber)
    host.addService(service)

def ospf(hostName, network = "***lan***", area = "***area***", *red):
    host = hosts[hostName]
    service = OspfService(network, area, CONN in red, BGP in red, RIP in red)
    host.addService(service)

class NoInterfaceSetup(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
        
class BadInterfaceSetup(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Host:
    def __init__(self, name):
        self.name = name
        self.interfaces = []

        self.services = []

    def addService(self, service):
        self.services.append(service)
        
    def addInterface(self, interface):
    	self.interfaces.append(interface)


class Service:
    def __init__(self):
        pass
    def checkIfFileContains(self, fileName, string):
        fil = open(fileName, "r")
        content = fil.read()
        fil.close()
        return string in content

    def addStringIfNotPresentInFile(self, fileName, string):
        if not self.checkIfFileContains(fileName, string):
            f = open(fileName, "a")
            f.write("\n"+string+"\n")
            f.close()

    def mkdirForHost(self, hostName, folder):
        path = "%s/%s" % (hostName, folder)
        if not os.path.exists(path):
            os.makedirs(path)

    def applyService(self, hostName):
        pass


class BindService(Service):
    def __init__(self, authFor):
        self.authFor = authFor

    def makeNamed(self, hostName, content):
        f = open("%s/etc/bind/named.conf", "w")
        f.write(content)
        f.close()

    def applyService(self, hostName):
        self.mkdirFor(self, hostName, "etc/bind")
        if self.authFor:
            makeNamed(NAMED_AUTH % ("hint", self.authFor))
    

class ZebraService(Service):
    def __init__(self):
        pass

    def startZebra(self, hostName):
        self.addStringIfNotPresentInFile("%s.startup" % (hostName), ZEBRA_START)

    def createZebraFolder(self, hostName):
        self.mkdirForHost(hostName, "etc/zebra")

    def addDaemon(self, hostName, daemonName):
        if not os.path.exists("%s/etc/zebra/daemons" % (hostName)):
            os.system("touch %s/etc/zebra/daemons" % (hostName))
        self.addStringIfNotPresentInFile("%s/etc/zebra/daemons" % (hostName), "zebra=yes")
        self.addStringIfNotPresentInFile("%s/etc/zebra/daemons" % (hostName), "%s=yes" % (daemonName))

class BgpService(ZebraService):
    def __init__(self, ASNumber):
        self.asn = ASNumber

    def applyService(self, hostName):
        self.startZebra(hostName)
        self.createZebraFolder(hostName)
        self.addDaemon(hostName, "bgpd")

        f = open("%s/etc/zebra/bgpd.conf" % (hostName), "w")
        f.write(BGP_FILE % (self.asn))
        f.close()



class RipService(ZebraService):
    def __init__(self, network, connected, bgp, ospf):
        self.network = network
        self.connected = connected
        self.bgp = bgp
        self.ospf = ospf

    def applyService(self, hostName):
        self.startZebra(hostName)
        self.createZebraFolder(hostName)
        self.addDaemon(hostName, "ripd")

        fileContent = RIP_FILE % (self.network)
        if self.connected:
            fileContent += "\n"+"redistribute connected"+"\n"
        if self.bgp:
            fileContent += "\n"+"redistribute bgp"+"\n"
        if self.ospf:
            fileContent += "\n"+"redistribute ospf"+"\n"

        f = open("%s/etc/zebra/ripd.conf" % (hostName), "w")
        f.write(fileContent)
        f.close()

class OspfService(ZebraService):
    def __init__(self, network, area, connected, bgp, rip):
        self.network = network
        self.area = area
        self.connected = connected
        self.bgp = bgp
        self.rip = rip

    def applyService(self, hostName):
        self.startZebra(hostName)
        self.createZebraFolder(hostName)
        self.addDaemon(hostName, "ospfd")

        fileContent = OSPF_FILE % (self.network, self.area)
        if self.connected:
            fileContent += "\n"+"redistribute connected"+"\n"
        if self.bgp:
            fileContent += "\n"+"redistribute bgp"+"\n"
        if self.rip:
            fileContent += "\n"+"redistribute rip"+"\n"

        f = open("%s/etc/zebra/ospfd.conf" % (hostName), "w")
        f.write(fileContent)
        f.close()

    

class Interface:
    def __init__(self, interfaceNumber, ipAndNetmaskLength):
        self.interfaceNumber = interfaceNumber
        self.ipAndNetmaskLength = ipAndNetmaskLength
        # a map (<prefix> -> <gateway>) for gateways reachable from this interface
        # for packets whose destination is <prefix>
        self.destination2gateway = {}

    

def isNumber(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def getFileLines(fileName):
    f = open(fileName, "r")
    lines = f.readlines()
    lines = map(lambda s: s.replace('\n', ''), lines)
    f.close()
    return lines
    
def getInterfaceNumber(hostDeclaration): # gets a string like pc[0]=A, returns "0"
    interfaceNumber = hostDeclaration.split("]")[0].split("[")[1]
    if isNumber(interfaceNumber):
        return interfaceNumber
    raise BadInterfaceSetup("")

def getGatewaysFromString(networkDeclaration):
    prefs2gws = {}
    try:
        declarationElements = networkDeclaration.split(",") # from "gw - 100.0.0.1, 200.0.0.0/24 - 100.0.0.2"
                                                            # to ["gw - 100.0.0.1", "200.0.0.0/24 - 100.0.0.2""]

        for prefix2gateway in declarationElements:
            prefix2gateway = prefix2gateway.strip()
            prefix2gatewayElem = prefix2gateway.split("-")
            prefix = prefix2gatewayElem[0].strip()
            gateway = prefix2gatewayElem[1].strip()
            prefs2gws[prefix] = gateway
    except IndexError:
        raise BadInterfaceSetup("Error in gateway setup, wrong syntax")

    return prefs2gws
        
        
    
def getGateways(networkDeclaration):
    # if networkDeclaration Contains "to:" we have a valid
    # declaration of gateways
    gateways = {} 
    networkDeclaration = networkDeclaration.strip()
    if "to:" in networkDeclaration:
        networkDeclaration = networkDeclaration.replace("to:", "")
        gateways = getGatewaysFromString(networkDeclaration)
    else:
        raise BadInterfaceSetup("Error in gateways setup \"to:\" is missing")

    return gateways
    
def getInterfaceDataFromLine(line):
    interface = None
	
    lineElements = line.split("#")
    if len(lineElements) < 2: 		# dovrebbe essere pc[0]=A   #100.0.0.2/24
        raise NoInterfaceSetup("")
    try:
        ipAndGateways = lineElements[1].split(";") # da 100.0.0.1/24; to: gw - 100.0.0.1
                                                   # a ['100.0.0.1/24', 'to:100.0.0.1']


        ipAndNetmaskLength = ipAndGateways[0].strip()
        # ottieni il numero di interfaccia
        interfaceNumber = getInterfaceNumber(lineElements[0])
        
        interface = Interface(interfaceNumber, ipAndNetmaskLength)

        if len(ipAndGateways) > 1 and ipAndGateways[1].strip() != "":  # potrebbe non esserci ";" o c'e' ma non c'e' nulla dopo
            interfaceGateways = getGateways(ipAndGateways[1])
            interface.destination2gateway = interfaceGateways
	
    except IndexError:
        raise BadInterfaceSetup("")
        
    return interface
	

def getHostNameFromLine(line):
    lineElements = line.split('[')
    if len(lineElements) > 1:
        return lineElements[0]
    else:
        return None

def isInterfaceSetup(line):
    try:
        return line.index("#") != 0
    except ValueError:
        return False

def isFunctionCall(line):
    try:
        return line.index("#") == 0
    except ValueError:
        return False


def configureInterfaceForHost(hostName, line): # line is needed to get informations about
                                               # the interface configuration
    currentHost = None
    if hostName != None:
        if hostName in hosts:
            currentHost = hosts[hostName]
        else:
            currentHost = Host(hostName)
            hosts[hostName] = currentHost

        
        interface = None
        
        interface = getInterfaceDataFromLine(line)

        if interface != None:
            currentHost.addInterface(interface)
        

def getHosts(labFile):
    lines = getFileLines(labFile)
    lineCounter = 1
    for line in lines:
        hostName = getHostNameFromLine(line)
        if hostName != None and not hostName in hosts:
            # declares a local variable whose name and value is hostName
            try:
                exec "%s = \"%s\"" % (hostName, hostName)
            except SyntaxError:
                print "-warning (nothing bad): cannot declare symbol %s, use quotes when using this host in configuration functions: e.g. bgp(\"%s\", 5) instead of bgp(%s, 5)" % (hostName, hostName, hostName)
            
            
        if isInterfaceSetup(line):
            print "working on %s" % (hostName)
            try:
                configureInterfaceForHost(hostName, line)
            except NoInterfaceSetup:
                print "-warning: no interface setup in line %i" % (lineCounter)
            except BadInterfaceSetup, e:
                print "-warning: bad interface setup in line %i:\n   %s" % (lineCounter, e.value)

        # a command like #bgp(...) or #rip(...)
        elif isFunctionCall(line):
            try:
                exec line[1:]
            except Exception, e:
                print "-Error in line %i: %s\n\t%s" % (lineCounter, line, str(e))
        		
            

        lineCounter += 1

    return hosts.values()


def configInterfacesAddress(host):
    f = open("%s.startup" % (host.name), "w")
    for interface in host.interfaces:
        ifconfig = IFCONFIG_COMMAND % (interface.interfaceNumber, interface.ipAndNetmaskLength)

        f.write(ifconfig)
        
        for prefix, gateway in interface.destination2gateway.iteritems():
            if prefix == "dfgw":
                command = DEFAULT_COMMAND % (gateway, interface.interfaceNumber)
            else:
                command = ROUTE_COMMAND % (prefix, gateway, interface.interfaceNumber)

            f.write(command)

        
    f.close()


def writeFile(path, content, mode = "w"):
    f = open(path, mode)
    f.write(content)
    f.close()

def createConfFile(labFile):
    f = open("lab.conf", "w")
    lines = getFileLines(labFile)
    for line in lines:
        lineToWrite = line
        try:
            pos = line.index("#")
            lineToWrite = line[:pos]
        except ValueError:
            pass
        f.write(lineToWrite + "\n")
    f.close()

def configureServices(host):
    for service in host.services:
        service.applyService(host.name)

def createLabFoldersAndFiles(labFile):
    hosts = getHosts(labFile)
    for host in hosts:
        os.system("mkdir %s" % (host.name))
        os.system("touch %s.startup" % (host.name))
        configInterfacesAddress(host)
        configureServices(host)

    createConfFile(labFile)

createLabFoldersAndFiles("lab.confu")
