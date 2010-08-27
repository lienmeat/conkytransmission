#!/usr/bin/env python

# conkytransmission.py by Eric Lien
# Designed to scrape torrent data from transmission-remote (on localhost) and output the data in a format
# that looks good with conkycolors themes.
# License is creative commons...give me some credit
#
# To make this work:
# 1) install conky
# 2) install transmission-cli and uninstall transmission-daemon
#    if installed, the web interface for transmission must be enabled as well
# 3) in your ~/.conkyrc file, ABOVE the TEXT area, you will need to add a line like:
#    lua_load /path/to/conkytransmission.lua
# 4) add a line like:
#    ${execpi 3 /path/to/conkytransmission.py}
#    to your ~/.conkyrc file below the TEXT area

#tested on ubuntu 10.04 x86_64 with python v2.6.5 and conky v1.8.0 (conky-all package)

__author__="Eric Lien"
__date__ ="$Aug 20, 2010 6:30:03 PM$"
__version__="0.2 beta"

import os
import sys
import codecs
from optparse import OptionParser
from subprocess import Popen, PIPE
from operator import attrgetter
from datetime import datetime

class CommandLineParser:

    parser = None

    def __init__(self):
        self.parser = OptionParser()
        self.parser.add_option("-a","--showactive", dest="show_active", default=False, action="store_true", help=u"Show only active torrents")
        self.parser.add_option("--case_sensitive", dest="case_sensitive_filter", default=False, action="store_true", help=u"Make the keyword filter case sensitive")
        self.parser.add_option("-e","--extradata", dest="extra_data", default=False, action="store_true", help=u"Get extra torrent data (runs a command for every torrent to get more data, slower)")
        self.parser.add_option("-f","--filterlist", dest="filter_file", default=False, metavar="FILE", help=u"File containing keywords to filter out torrents with. If the keyword is found in a torrent name, that torrent will not be shown.")
        self.parser.add_option("-k","--kbps",dest="k_unit", default="K", type="string", metavar="STRING", help=u"How you would like KiB/s to be shown [default: %default]")
        self.parser.add_option("-l","--namelength",dest="name_length", type="int", default=35, metavar="NUMBER", help=u"[default: %default] Length of torrent name in characters")
        self.parser.add_option("-n","--number",dest="number", default=99, type="int", metavar="NUMBER", help=u"How many torrents will be shown [default: %default]")
        self.parser.add_option("-m","--mbps",dest="m_unit", default="M", type="string", metavar="STRING", help=u"How you would like MiB/s to be shown [default: %default]")
        self.parser.add_option("-r","--reverse", dest="reverse_sort", default=False, action="store_true", help=u"Sort in reverse order")
        self.parser.add_option("-s","--sortby", dest="sort_by", default="progress", type="string", metavar="option", help=u"How torrents are sorted. [default: %default] options=(percent,eta,down,up,ratio,status,progress,name)")
        self.parser.add_option("-t","--templatespath", dest="template_folder", default=False, metavar="PATH", help=u"Folder where your custom templates are")
        self.parser.add_option("-v", "-V", "--version", dest="version", default=False, action="store_true", help=u"Displays the version of the script.")  
        
    def parse_args(self):
        (options, args) = self.parser.parse_args()
        #it's possible they entered in something stupid into the sortby field...
        sort_options = ['percent','eta','down','up','ratio','status','progress','name']
        try:
            i = sort_options.index(options.sort_by)
        except Exception, e:
            options.sort_by = "progress"
        options.base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
        return (options, args)

    def print_help(self):
        return self.parser.print_help()

class ConkyTransmission:
    """Gets transmission information and forms conky scripts from it"""
    config = None
    torrent_list = list()
    filter_list = list()
    templater = None
    
    def __init__(self, config):
        self.config = config
        self.getFilterList()                  
        try:
            self.templater = TemplateWriter(config)
        except Exception:
            print "Could not find templates! Quitting!"
        else:
            self.run()
    
    #parses filter_file for keywords, putting them in a list
    def getFilterList(self):
        if self.config.filter_file:            
            filtertext = getFile(self.config.filter_file)
            if filtertext and len(filtertext) > 0:
                filtertext = filtertext.replace(' ','').replace('\n','')
                if not self.config.case_sensitive_filter:
                    filtertext = filtertext.lower()
                self.filter_list = str(filtertext).split(",")
    
    #checks for filter words in torrent name
    def hasFilterWord(self, torrent):
        if self.config.case_sensitive_filter:
            name = torrent.name                    
        else:
            name = torrent.name.lower()

        for w in self.filter_list:
            if name.find(w) >= 0:
                return True
        return False
    
    # scrape data from transmission-remote, separating lines
    # returns list of lines of transmission-remote -l
    def scrapeTransmission(self):
        return getCommandOutput(["transmission-remote", "-l"])
        
    # Gathers output for conky into variables
    def getTorrentData(self):
        havetorrents = False
        torrent_lines = self.scrapeTransmission()
        length = len(torrent_lines)
        count = 1
        for t in torrent_lines:
            #for lines that contain data about torrents
            if count > 1 and count < length:
                t = Torrent(t, self.config)
                if self.config.show_active:
                    if(t.status == "Seeding" or t.status == "Downloading" or t.status == "Up & Down" and not self.hasFilterWord(t)):
                        if self.config.extra_data:
                            t.setExtraData(self.getExtraData(t))
                        self.torrent_list.append(t)
                        havetorrents = True
                elif(not self.hasFilterWord(t)):
                    if self.config.extra_data:
                        t.setExtraData(self.getExtraData(t))
                    havetorrents = True
                    self.torrent_list.append(t)
            #last line has relevent global stats
            elif count == length:
                #store global stats
                self.getGlobalStats(t)
            count = count + 1
        return havetorrents
        
    def getExtraData(self, torrent):
        if self.config.extra_data:
            return getCommandOutput(["transmission-remote", "-t", str(torrent.id), "-i"])
            
    #sort logic wrapper
    #calls multiple sort methods      
    def sortTorrents(self):
        sb = self.config.sort_by
        if sb == "eta":
            self.simpleSort("eta_seconds")
        elif sb == "name":
            self.simpleSort("name")
        elif sb == "progress":
            self.sortByProgress()
        else:
            self.simpleSort(sb)
    
    #only sorts one field, no advanced sorting        
    def simpleSort(self, field):
        sortover = "torrent."+field
        self.torrent_list = sorted(self.torrent_list, key=lambda torrent: eval(sortover), reverse=self.config.reverse_sort)
    
    #sorts by percent, then ratio
    def sortByProgress(self):
        self.torrent_list = sorted(self.torrent_list, key=attrgetter('percent', 'ratio'), reverse=True)    
        if self.config.reverse_sort:
            self.torrent_list.reverse()
    
    # Parses out global stats from last line of
    # transmission-remote -l output and forms 
    # conky script for it
    def getGlobalStats(self, info_line):
        out = ''
        #properties are separated by at least 2 spaces
        info_list = info_line.split("  ")
        count = 0
        for p in info_list:
            #strip extra white space
            p = p.lstrip().rstrip() 
            if p != '':
                count = count + 1
                # we only care about properties 3 and 4 (up and down speed)
                if count == 3:
                    self.total_up = p                      
                elif count == 4:
                    self.total_down = p
        
    
    # Runs the process from start to finish, printing data for conky
    def run(self):
        if self.getTorrentData():
            self.sortTorrents()
            #get rid of any torrents more than the configured max
            self.torrent_list = self.torrent_list[:self.config.number]
            self.templater.getTorrentOutput(self.torrent_list)
            self.templater.getGlobalsOutput(self.total_up, self.total_down)
            print self.templater.getOutput()
            
class Torrent:
    """Parses out torrent properties from a lines of output of transmission-remote"""
    id = None
    percent = None
    eta = None
    eta_seconds = None
    up = None
    down = None
    ratio = None
    status = None
    name = None
    location = None
    available = None
    size = None
    downloaded = None
    uploaded = None
    ratio_limit = None
    corrupt = None
    connected_to = None
    uploading_to = None
    downloading_from = None
    datetime_added = None
    datetime_started = None
    datetime_latest_activity = None
    public_torrent = None
    pieces = None
    piece_size = None
    

    # parses an input line of torrent properties into
    # class variables
    def __init__(self, properties, config):
        self.config = config
        properties = properties.split("  ")
        count = 0
        for p in properties:
            p = p.lstrip().rstrip()
            if p != '':
                #convert non-blanks into proper format
                count = count + 1
                if count == 1:
                    self.setId(p)
                elif count == 2:
                    self.setPercent(p)
                elif count == 4:
                    self.setETA(p)
                elif count == 5:
                    self.up = p
                elif count == 6:
                    self.down = p
                elif count == 7:
                    self.ratio = p
                elif count == 8:
                    self.status = p
                elif count == 9:
                    self.name = p
        #for some crazy reason, sometimes transmission-remote returns
        #the wrong status
        if self.status == "Up & Down" and float(self.down) < 0.1:
            self.status = "Seeding"
        if self.status == "Up & Down" and float(self.up) < 0.1:
            self.status = "Downloading"
        if self.status == "Seeding" and float(self.up) < 0.1:
            self.status = "Idle"
        elif self.status == "Downloading" and float(self.down) < 0.1:
            self.status = "Idle"
            
    def setExtraData(self, data):
        for l in data:
            if self.setLocation(l): continue
            if self.setAvailable(l): continue
            if self.setSize(l): continue
            if self.setDownloaded(l): continue
            if self.setUploaded(l): continue
            if self.setRatioLimit(l): continue
            if self.setCorrupt(l): continue
            if self.setPeers(l): continue
            if self.setDateAdded(l): continue
            if self.setDateStarted(l): continue
            if self.setLatestActivity(l): continue
            if self.setPublicTorrent(l): continue
            if self.setPieces(l): continue
            if self.setPieceSize(l): continue

    def getValue(self, line, remove):
        return line.replace(remove, "").strip()
            
    def setLocation(self, line):
        if self.location == None:
            if line.find("Location:") >= 0:
                self.location = self.getValue(line, "Location: ")
                return True       
    
    def setAvailable(self, line):
        if self.available == None:
            if line.find("Availability:") >= 0:
                self.available = self.getValue(line, "Availability: ")
                return True
                
    def setSize(self, line):
        if self.size == None:
            if line.find("Total size:") >= 0:
                idx1 = line.find("(")
                idx2 = line.find(")")
                self.size = line[idx1+1:idx2].replace(" wanted", '')
                return True
            
    def setDownloaded(self, line):
        if self.downloaded == None:
            if line.find("Downloaded:") >= 0:
                self.downloaded = self.getValue(line, "Downloaded: ")
                return True

    def setUploaded(self, line):
        if self.uploaded == None:
            if line.find("Uploaded:") >= 0:
                self.uploaded = self.getValue(line, "Uploaded: ")
                return True
            
    def setRatioLimit(self, line):
        if self.ratio_limit == None:
            if line.find("Ratio Limit:") >= 0:
                self.ratio_limit = self.getValue(line, "Ratio Limit: ")
                return True
            
    def setCorrupt(self, line):
        if self.corrupt == None:
            if line.find("Corrupt DL:") >= 0:
                self.corrupt = self.getValue(line, "Corrupt DL: ")
                return True
            
    def setPeers(self, line):
        if self.connected_to == None:
            if line.find("Peers:") >= 0:
                peers = self.getValue(line, "Peers: ").split(", ")
                self.connected_to = peers[0].replace("connected to ", '').strip()
                self.uploading_to = peers[0].replace("uploading to ", '').strip()
                self.downloading_from = peers[0].replace("downloading from ", '').strip()
                return True
                
    def setDateAdded(self, line):
        if self.datetime_added == None:
            if line.find("Date added:") >= 0:
                self.datetime_added = datetime.strptime(self.getValue(line, "Date added: "), "%a %b %d %H:%M:%S %Y")
                return True

    def setDateStarted(self, line):
        if self.datetime_started == None:
            if line.find("Date started:") >= 0:
                self.datetime_started = datetime.strptime(self.getValue(line, "Date started: "), "%a %b %d %H:%M:%S %Y")
                return True
        
    def setLatestActivity(self, line):
        if self.datetime_latest_activity == None:
            if line.find("Latest activity:") >= 0:
                self.datetime_latest_activity = datetime.strptime(self.getValue(line, "Latest activity: "), "%a %b %d %H:%M:%S %Y")
                return True
    
    def setPublicTorrent(self, line):
        if self.public_torrent == None:
            if line.find("Public torrent:") >= 0:
                self.public_torrent = self.getValue(line, "Public torrent: ")
                return True
                
    def setPieces(self, line):
        if self.pieces == None:
            if line.find("Piece Count:") >= 0:
                self.pieces = self.getValue(line, "Piece Count: ")
                return True
    
    def setPieceSize(self, line):
        if self.piece_size == None:
            if line.find("Piece Size:") >= 0:
                self.piece_size = self.getValue(line, "Piece Size: ")
                return True

    # sets id of torrent
    def setId(self, str):
        self.id = int(str.strip("*"))

    # sets percent downloaded
    def setPercent(self, str):
        self.percent = int(str.strip("%"))

    # sets estimated time left
    def setETA(self, str):
        if str == 'Unknown':
            self.eta = "?"
        else:
            self.eta = str
        self.setETASeconds(str)    
            
    #sets the ETA in seconds (so we can sort them by eta)
    def setETASeconds(self, eta):
        if eta.find("secs") > 0:
            self.eta_seconds = int(eta.strip(' secs'))
        elif eta.find("min") > 0:
            self.eta_seconds = 60 * int(eta.strip(' mins'))
        elif eta.find("hrs")  > 0:
            self.eta_seconds = 3600 * int(eta.strip(' hrs'))
        elif eta.find("days")  > 0:
            self.eta_seconds = 86400 * int(eta.strip(' days'))
        elif eta == "Done":
            self.eta_seconds = 0
        else:
            self.eta_seconds = 9999999999999999
            
class TemplateWriter:
    """Finds and writes to the templates"""
    config = None
    path = ''
    layout = None
    globals_template = None 
    torrent_default = None
    loaded_templates = dict()
    missing_templates = list()
    globals_output = ""
    torrent_output = ""
    
    def __init__(self, config):
        self.config = config
        if config.template_folder:
            self.path = config.template_folder
        else:
            self.path = config.base_path+"/templates"
        if not self.getCriticalTemplates():
            raise Exception("Critical templates missing!")
    
    def getCriticalTemplates(self):
        path = self.path
        self.layout = getFile(path+"/layout.template")
        self.globals_template = getFile(path+"/globals.template")
        self.torrent_default = getFile(path+"/torrent_default.template")
        if(self.layout and self.globals_template and self.torrent_default):
            return True
        else:
            return False
            
    def getOutput(self):
        if self.torrent_output != "":
            template = self.layout
            template = template.replace("[:TORRENTS:]", self.torrent_output.rstrip("\n"))
            template = template.replace("[:GLOBALS:]", self.globals_output.rstrip("\n"))
            return template
        else:
            return ""
            
    def getGlobalsOutput(self, up, down):
        template = self.globals_template
        template = template.replace("[:G_UP:]", self.getSpeed(up))
        template = template.replace("[:G_UP_KBPS:]", str(up))
        template = template.replace("[:G_DOWN:]", self.getSpeed(down))
        template = template.replace("[:G_DOWN_KBPS:]", str(down))
        self.globals_output = template        
    
    def getTorrentOutput(self, torrents):
        for torrent in torrents:
            template = self.getTorrentTemplate(torrent)
            torrent.name = torrent.name[:self.config.name_length]
            for p, v in torrent.__dict__.iteritems():
                template = template.replace("[:"+p.upper()+":]", str(v))
            template = template.replace("[:UP_KBPS:]", str(getSpeed(torrent.up, self.config.m_unit, self.config.k_unit)))
            template = template.replace("[:DOWN_KBPS:]", str(getSpeed(torrent.down, self.config.m_unit, self.config.k_unit)))
            #add additional template things here!
            self.torrent_output+=template        
        
    def getTorrentTemplate(self, torrent):
        template_name = "torrent_"+torrent.status.lower().replace(" ","_")
        try:
            template = self.loaded_templates[template_name]
        except KeyError:
            try:
                self.missing_templates.index(template_name)
            except ValueError:
                filename = template_name+".template"
                template = getFile(self.path+"/"+filename)
                if not template:
                    self.missing_templates.append(template_name)
                    return self.torrent_default
                else:
                    self.loaded_templates[template_name] = template
                    return template
            else:
                return self.torrent_default
        else:
            return template
            
    def getSpeed(self, v):
        return getSpeed(v, self.config.m_unit, self.config.k_unit)
    
# function formatting KiB/s output by transmission into
# a human readable but succinct format
def getSpeed(str, m_unit, k_unit):
    kbps = float(str)
    if kbps > 1024:
        speed = `round(float(kbps/1024), 2)`
        unit = m_unit
    else:
        speed = `round(kbps, 2)`
        unit = k_unit
    return speed[:(speed.find('.') + 2)] + " " + unit

def getFile(path):
    path = path.replace("//","/")
    try:
        fileinput = codecs.open(os.path.expanduser(path),encoding='utf-8')
        filedata = fileinput.read()
        fileinput.close()
    except Exception, e:
        return False
    else:
        return filedata
        
def getCommandOutput(command_list):
    p = Popen(command_list, stdout=PIPE, stderr=PIPE)
    output = p.communicate()[0]
    return output.splitlines()

if __name__ == "__main__":
    (options, args) = CommandLineParser().parse_args()
    if options.version:
        print "conkyTransmission v.0.2"
    else:    
        ConkyTransmission(options)
