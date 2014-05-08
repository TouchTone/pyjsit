#!/usr/bin/python

import operator, copy, os, sys, threading, cStringIO, traceback
from PySide.QtCore import *
from PySide.QtGui import *

import preferences
pref = preferences.pref


from log import *
from tools import unicode_cleanup

import jsitwindow 
import TorrentTable 

import jsit_manager
import jsit


qApp = None

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
        self.ui.watchClipboard.stateChanged.connect(self.watchClipboard)
        self.ui.watchDirectory.stateChanged.connect(self.watchDirectory)

        self.ui.actionSave_Preferences.activated.connect(self.savePreferences)
        self.ui.actionEdit_Preferences.activated.connect(self.NIY)
        
        
        # Set up values from preferences
        self.ui.watchClipboard.setChecked(bool(pref("jsit_manager", "watchClipboard", False)))
        self.ui.watchDirectory.setChecked(bool(pref("jsit_manager", "watchDirectory", False)))
        
                
    
    def __repr__(self):
        return "JSITWindow(0x%x)" % id(self)
   
   
    def closeStartBox(self):
        self._startBox.close()
        self._startBox = None
        
   
    def update(self):
        log(DEBUG)
         
        try:
            clip = unicode_cleanup(self._clip.text(QClipboard.Clipboard)).encode("ascii", 'replace')
            sel  = unicode_cleanup(self._clip.text(QClipboard.Selection)).encode("ascii", 'replace')
            self.model.update(clip = [clip, sel])
            
            # self.model.updateAttributes(self.ui.tableView) Still needed? Shouldn't...
 
        finally:
            if self._visible:
                QTimer.singleShot(pref("main", "updateRate", 1000), self.update)

            
    def addTorrentFiles(self):
        log(INFO)
        fns,ftype = QFileDialog.getOpenFileNames(self, "Open Torrent File", "", "Torrent Files (*.torrent)")
        
        for fn in fns:
            tor = self.mgr.addTorrentFile(fn, basedir=pref("downloads", "basedir", "downloads"), maximum_ratio = pref("jsit", "maximumRatioPublic", 1.5), 
                                            unquoteNames=pref("downloads", "unquoteNames", True), interpretDirectories=pref("downloads", "interpretDirectories", True))
                                        
            if tor.private:
                tor.maximum_ratio = pref("jsit", "maximumRatioPrivate", 5.0)
            
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
            tor = self.mgr.addTorrentURL(url, basedir=pref("downloads", "basedir", "downloads"), maximum_ratio=pref("jsit", "maximumRatio", 1.5), 
                                            unquoteNames=pref("downloads", "unquoteNames", True), interpretDirectories=pref("downloads", "interpretDirectories", True))       
                                        
            if tor.private:
                tor.maximum_ratio = pref("jsit", "maximumRatioPrivate", 5.0)
        
    def startAll(self):
        log(INFO)
        
        self.mgr.startAll()        
    
    
    def stopAll(self):
        log(INFO)
        
        self.mgr.stopAll()        
 
 
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
    
    versionInfo = "0.3.0"
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
    
    ret = QMessageBox.question(None, "Unhandled Exception Caught!", str(notice)+str(msg)+str(versionInfo), QMessageBox.Ok | QMessageBox.Cancel )
    
    if ret == QMessageBox.Cancel:
        os._exit(1) # Brute force exit, avoid thread problems...
        
    exception_active = False
  
  
sys.excepthook = excepthook
 
if __name__ == "__main__":
    
    global basedir

    if len(sys.argv) < 1:
        print "Call as %s" % sys.argv[0]
        sys.exit(1)

    if getattr(sys, 'frozen', None):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)

    if os.path.isfile(os.path.join(basedir, "preferences.json")):
        preferences.load(os.path.join(basedir, "preferences.json"))
    else:
        preferences.load(os.path.join(basedir, "defaults.json"))


    setLogLevel(pref("main", "logLevel", INFO))
    setFileLog(os.path.join(basedir, "yajsig.log"), pref("main", "fileLogLevel", DEBUG))

    global qapp    
    qapp = QApplication([])


    if len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]
        log(DEBUG, "Got %s:%s from command line." % (username, password))
    else:
        username = pref("jsit", "username", "")
        password = pref("jsit", "password", "")        
        log(DEBUG, "Got %s:%s from preferences." % (username, password))

        if username == None or password == None:
            log(DEBUG, "Need username and password, trigger input.")
            raise jsit.APIError

    while True:
        try:

            mgr = jsit_manager.Manager(username = username, password = password, torrentdir = pref("jsit", "torrentDirectory", "intorrents"))

            break
            
        except Exception, e:
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

    # Hack... Windows doesn't set cwd, so local paths go wrong
    if not mgr._torrentDirectory.startswith(os.path.sep) and not mgr._torrentDirectory[1] == ':':
        mgr._torrentDirectory = os.path.join(basedir, mgr._torrentDirectory)
    d = pref("downloads", "basedir", "downloads")
    if not d.startswith(os.path.sep) and not d[1] == ':':
        d = os.path.join(basedir, d)
        preferences.setValue("downloads", "basedir", d)

    # For testing limit logging...
    ##addIgnoreModule("jsit")
    ##addIgnoreModule("jsit_manager")
    ##addOnlyModule("TorrentTable")


    # Put up a Splash Screen
    splash_pix = QPixmap('yajsig_splash.png')
    sc = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    sc.show()
    qapp.processEvents();
    qapp.processEvents();


    win = JSITWindow(mgr)

    QObject.connect(qapp, SIGNAL("lastWindowClosed()"), win, SLOT("quit()"))

    win.show()
    sc.finish(win)

    qapp.exec_()
