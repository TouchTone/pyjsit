#!/usr/bin/python

import operator, copy, os, sys, threading, cStringIO, traceback
import gc
from PySide.QtCore import *
from PySide.QtGui import *

import preferences
pref = preferences.pref
prefDir = preferences.prefDir


from log import *
from tools import unicode_cleanup

import jsitwindow 
import TorrentTable 

import jsit_manager
import jsit


VERSION="0.5.0" # Adjusted by make_release

qApp = None


# From http://pydev.blogspot.com.br/2014/03/should-python-garbage-collector-be.html

class GarbageCollector(QObject):
    '''
    Disable automatic garbage collection and instead collect manually
    every INTERVAL milliseconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash.
    '''

    INTERVAL = 3000

    def __init__(self, parent, debug=False):
        QObject.__init__(self, parent)
        self.debug = debug

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        if self.debug:
            print ('gc thresholds:', self.threshold)
            
        gc.disable()
        self.timer.start(self.INTERVAL)

    def check(self):
        #return self.debug_cycles() # uncomment to just debug cycles
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print 'gc_check called:', l0, l1, l2
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print 'collecting gen 0, found:', num, 'unreachable'
            if l1 > self.threshold[1]:
                #gc.set_debug(gc.DEBUG_LEAK)
                num = gc.collect(1)
                if self.debug:
                    print 'collecting gen 1, found:', num, 'unreachable'
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print 'collecting gen 2, found:', num, 'unreachable'

    def debug_cycles(self):
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))
            
            
            
            
class JSITWindow(QMainWindow):
    def __init__(self, mgr, *args):
    
        QMainWindow.__init__(self, *args)        
 
        self.mgr = mgr
        
        self.ui = jsitwindow.Ui_JSIT()
        self.ui.setupUi(self)
       
        self._visible = True
         
        self.model = TorrentTable.TorrentTableModel(self, mgr)
        self.ui.tableView.setDataModel(self.model)   
    
        self._clip = QApplication.clipboard()
        
        # Set up routes to my methods
        self.ui.addFiles.clicked.connect(self.addTorrentFiles)
        self.ui.addURL.clicked.connect(self.addTorrentURL)
        self.ui.startB.clicked.connect(self.startAll)
        self.ui.stopB.clicked.connect(self.stopAll)
        self.ui.downloadB.clicked.connect(self.downloadAll)
        self.ui.watchClipboard.stateChanged.connect(self.watchClipboard)
        self.ui.watchDirectory.stateChanged.connect(self.watchDirectory)
        self.ui.reloadB.clicked.connect(self.reloadList)

        self.ui.actionSave_Preferences.activated.connect(self.savePreferences)
        self.ui.actionEdit_Preferences.activated.connect(self.NIY)
        self.ui.actionAbout.activated.connect(self.about)
        
        # Set up values from preferences
        self.ui.watchClipboard.setChecked(bool(pref("jsit_manager", "watchClipboard", False)))
        self.ui.watchDirectory.setChecked(bool(pref("jsit_manager", "watchDirectory", False)))
        
        # Set up log catching for errors
        ## Not threadsafe...
        ##addLogCallback(self.logError)
        
    
    def __repr__(self):
        return "JSITWindow(0x%x)" % id(self)
   
   
    def closeStartBox(self):
        self._startBox.close()
        self._startBox = None
        
   
    def update(self):
        log(DEBUG)
         
        try:
            self.model.update(clip = [self._clip.text(QClipboard.Clipboard), self._clip.text(QClipboard.Selection)])
 
        finally:
            QTimer.singleShot(pref("yajsig", "updateRate", 1000), self.update)

            
    def addTorrentFiles(self):
        log(INFO)
        fns,ftype = QFileDialog.getOpenFileNames(self, "Open Torrent File", "", "Torrent Files (*.torrent)")
        
        for fn in fns:
            tor = self.mgr.addTorrentFile(fn, basedir=pref("downloads", "basedir", "downloads"), 
                                            unquoteNames=pref("downloads", "unquoteNames", True), interpretDirectories=pref("downloads", "interpretDirectories", True))

                                            
    def addTorrentURL(self):
        log(INFO)

        dlg = QInputDialog(self)                 
        dlg.setInputMode(QInputDialog.TextInput) 
        dlg.setLabelText("Enter http/magnet link:")                        
        dlg.setWindowTitle("Add Torrent from URL")                        
        dlg.resize(500,100)                             
        ok = dlg.exec_()                                
        url = dlg.textValue()  
        
        if ok:
            tor = self.mgr.addTorrentURL(url, basedir=pref("downloads", "basedir", "downloads"), 
                                            unquoteNames=pref("downloads", "unquoteNames", True), interpretDirectories=pref("downloads", "interpretDirectories", True))       
                                        
         
    def startAll(self):
        log(INFO)
        
        self.mgr.startAll()        
    
    
    def stopAll(self):
        log(INFO)
        
        self.mgr.stopAll()        
    
    
    def downloadAll(self):
        log(INFO)
        
        self.mgr.downloadAll()                
 
    
    def reloadList(self):
        log(INFO)
        
        self.mgr.reloadList()        
 
 
    def watchClipboard(self, value):
        log(INFO)
        self.mgr.watchClipboard(bool(value))
        preferences.setValue("jsit_manager", "watchClipboard", bool(value))
        
 
    def watchDirectory(self, value):
        log(INFO)
        self.mgr.watchDirectory(bool(value))
        preferences.setValue("jsit_manager", "watchDirectory", bool(value))
    
    
    def showEvent(self, event):
        log(DEBUG)
        self._visible = True
        QTimer.singleShot(0, self.update)
     
    
    def hideEvent(self, event):
        log(DEBUG)
        self._visible = False

    
    def quit(self):
        log(WARNING)
               
        cpref = preferences.changed()
        
        # Somehow the MBox doesn't close. Figure out later.
        if False and cpref:
            b = QMessageBox(flags = Qt.Dialog);
            b.setText("Unsaved preferences")
            b.setInformativeText("The preferences %s have changed."% cpref)
            b.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel);
            b.setDefaultButton(QMessageBox.Save);
            ret = b.exec_();
            
            log(DEBUG, "ret= %s"% ret)
        
            if ret == QMessageBox.Save:       
                event.handled()
                self.savePreferences()
            elif ret == QMessageBox.Cancel:
                event.ignore()
            elif ret == QMessageBox.Disacrd:
                event.handled()
            else:
                log(WARNING, "Messagebox returned %s, not sure what to do." % ret)
        else:
            self.savePreferences()

        log(WARNING, "Quitting.")
        
        self.mgr.release()
        
        qApp.quit()

    
    def savePreferences(self):
        log(INFO)
        preferences.save(os.path.join(basedir, "preferences.json"))
        
    
    def NIY(self):
        log(INFO)
        b = QMessageBox();
        b.setText("Sorry!")
        b.setInformativeText("Not implemented yet...")
        b.setStandardButtons(QMessageBox.Ok);
        b.setDefaultButton(QMessageBox.Ok);
        ret = b.exec_();
    
    def about(self):
        log(INFO)
        b = QMessageBox();
        b.setText("About YAJSIG")
        b.setInformativeText("Yet Another Justseed.it GUI\nVersion %s" % VERSION)
        b.setStandardButtons(QMessageBox.Ok);
        b.setDefaultButton(QMessageBox.Ok);
        ret = b.exec_();
       
    
    def logError(self, fullmsg, threadName, ltime, level, levelName, caller, msg):
        if level > ERROR:   
            return
            
        log(INFO)
    
        ret = QMessageBox.question(None, "Error Caught!", str(msg), QMessageBox.Ok | QMessageBox.Abort)
        
        if ret == QMessageBox.Abort:
            os._exit(1) # Brute force exit, avoid thread problems...
        


# Exception catchall helper
# Based on http://www.riverbankcomputing.com/pipermail/pyqt/2009-May/022961.html (originally from Eric IDE)

exception_active = False

def excepthook(excType, excValue, tracebackobj):
    """
    Global function to catch unhandled exceptions.
    
    @param excType exception type
    @param excValue exception value
    @param tracebackobj traceback object
    """
    # Not reentrant, ignore everything after the first
    global exception_active
    if exception_active:
        return
        
    separator = '-' * 80
    logFile = "simple.log"
    notice = \
        """An unhandled exception occurred. Please report the problem\n"""\
        """at https://github.com/TouchTone/pyjsit/issues .\n"""\
        """Please include the 'yajsig.log' and 'aria.log' log files in your report.\n\nError information:\n"""
    
    timeString = time.strftime("%Y-%m-%d, %H:%M:%S")    
    
    tbinfofile = cStringIO.StringIO()
    traceback.print_tb(tracebackobj, None, tbinfofile)
    tbinfofile.seek(0)
    tbinfo = tbinfofile.read()
    errmsg = '%s: \n%s' % (str(excType), str(excValue))
    sections = [separator, timeString, separator, errmsg, separator, tbinfo]
    msg = '\n'.join(sections)
    
    log(ERROR, "Caught unhandled exception %s!" % errmsg)
    log(ERROR, tbinfo)

    exception_active = True
    
    ret = QMessageBox.question(None, "Unhandled Exception Caught!", str(notice)+str(msg)+str(VERSION), QMessageBox.Ok | QMessageBox.Abort)
    
    if ret == QMessageBox.Abort:
        os._exit(1) # Brute force exit, avoid thread problems...
        
    exception_active = False
  
  
# Not threadsafe...
##sys.excepthook = excepthook    

if __name__ == "__main__":
    
    global basedir

    if len(sys.argv) < 1:
        print "Call as %s" % sys.argv[0]
        sys.exit(1)

    if getattr(sys, 'frozen', None):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)

    preferences.setBaseDir(basedir)
    
    if os.path.isfile(os.path.join(basedir, "preferences.json")):
        preferences.load(os.path.join(basedir, "preferences.json"))
    else:
        preferences.load(os.path.join(basedir, "defaults.json"))


    setLogLevel(pref("yajsig", "logLevel", INFO))
    setFileLog(os.path.join(basedir, "yajsig.log"), pref("yajsig", "fileLogLevel", DEBUG))

    global qapp    
    qapp = QApplication([])

    # Make sure GC only runs in this thread to prevent crashes
    gcol = GarbageCollector(qapp, debug=False)
    

    if len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]
        log(DEBUG, "Got %s:%s from command line." % (username, password))
    else:
        username = pref("jsit", "username", None)
        password = pref("jsit", "password", None)        
        log(DEBUG, "Got %s:%s from preferences." % (username, password))

    while True:
        try:

            if username == None or password == None:
                log(DEBUG, "Need username and password, trigger input.")
                raise jsit.APIError("No user/password")

            mgr = jsit_manager.Manager(username = username, password = password, torrentdir = prefDir("jsit", "torrentDirectory", "intorrents"))

            break
            
        except jsit.APIError, e:
            log(WARNING, "JSIT login failed (%s)!" % e)

            username, ok = QInputDialog.getText(None, "JS.it Username", "Enter JS.it username:", QLineEdit.Normal, username)

            if not ok:
                log(ERROR, "Username aborted!")
                sys.exit(1)

            password, ok = QInputDialog.getText(None, "JS.it Password", "Enter JS.it password:", QLineEdit.Normal, password)

            if not ok:
                log(ERROR, "Password aborted!")
                sys.exit(1)

    log(DEBUG, "jsit_manager started...")

    preferences.setValue("jsit", "username", username)
    preferences.setValue("jsit", "password", password)

    ##addIgnoreModule("jsit")
    ##addIgnoreModule("jsit_manager")
    ##addOnlyModule("TorrentTable")

    win = JSITWindow(mgr)

    QObject.connect(qapp, SIGNAL("lastWindowClosed()"), win, SLOT("quit()"))

    win.show()
    
    if False:
        import stacktracer
        stacktracer.trace_start("trace.html",interval=5,auto=True) # Set auto flag to always update file!

    qapp.exec_()
