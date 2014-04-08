import operator, copy, os, sys
from PySide.QtCore import *
from PySide.QtGui import *

import preferences
pref = preferences.pref
prefOrVal = preferences.prefOrVal


from log import *

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
        
        # Set up update timer
        self._visible = True
 
    
    def __repr__(self):
        return "JSITWindow(0x%x)" % id(self)
   
   
    def update(self):
        log(DEBUG)
         
        try:
            self.model.update(clip = [str(self._clip.text(QClipboard.Clipboard)), str(self._clip.text(QClipboard.Selection))])
                        
            self.model.updateAttributes(self.ui.tableView)
 
        finally:
            if self._visible:
                QTimer.singleShot(pref("main", "updateRate"), self.update)

            
    def addTorrentFiles(self):
        log(INFO)
        fns,ftype = QFileDialog.getOpenFileNames(self, "Open Torrent File", "", "Torrent Files (*.torrent)")
        
        for fn in fns:
            tor = self.mgr.addTorrentFile(fn, basedir=pref("downloads", "basedir"), maximum_ratio = pref("jsit", "maximumRatioPublic"), 
                                            unquoteNames=pref("downloads", "unquoteNames"), interpretDirectories=pref("downloads", "interpretDirectories"))
                                        
            if tor.private:
                tor.maximum_ratio = pref("jsit", "maximumRatioPrivate")
            
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
            tor = self.mgr.addTorrentURL(url, basedir=pref("downloads", "basedir"), maximum_ratio=pref("jsit", "maximumRatio"), 
                                            unquoteNames=pref("downloads", "unquoteNames"), interpretDirectories=pref("downloads", "interpretDirectories"))       
                                        
            if tor.private:
                tor.maximum_ratio = pref("jsit", "maximumRatioPrivate")
        
    def startAll(self):
        log(INFO)
        
        self.mgr.startAll()        
    
    
    def stopAll(self):
        log(INFO)
        
        self.mgr.stopAll()        
 
 
    def watchClipboard(self, value):
        log(INFO)
        self.mgr.watchClipboard(value)
        
 
    def watchDirectory(self, value):
        log(INFO)
        self.mgr.watchDirectory(value)
    
    
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
            
            log(DEBUG, "ret= %s\n"% ret)
        
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
            
            
        qApp.quit()

    
    def savePreferences(self):
        log(INFO)
        preferences.save("preferences.json")
        
    
    def NIY(self):
        log(INFO)
        b = QMessageBox();
        b.setText("Sorry!")
        b.setInformativeText("Not implemented yet...")
        b.setStandardButtons(QMessageBox.Ok);
        b.setDefaultButton(QMessageBox.Ok);
        ret = b.exec_();


if __name__ == "__main__":
    

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
        
        
    setLogLevel(prefOrVal("main", "logLevel", INFO))
    setFileLog(os.path.join(basedir, "yajsig.log"), prefOrVal("main", "fileLogLevel", DEBUG))
    
    global qapp    
    qapp = QApplication([])


    try:

        if len(sys.argv) == 3:
            username = sys.argv[1]
            password = sys.argv[2]
        else:
            username = pref("jsit", "username")
            password = pref("jsit", "password")        
           
        mgr = jsit_manager.Manager(username = username, password = password)
        
    except jsit.APIError, e:
        log(WARNING, "JSIT login failed!\n")
        
        username, ok = QInputDialog.getText(None, "JS.it Username", "Enter JS.it username:", QLineEdit.Normal, username)
        
        if not ok:
            log(ERROR, "Username aborted!\n")
            sys.exit(1)
        
        password, ok = QInputDialog.getText(None, "JS.it Password", "Enter JS.it password:", QLineEdit.Normal, password)
        
        if not ok:
            log(ERROR, "Password aborted!\n")
            sys.exit(1)
        
        mgr = jsit_manager.Manager(username = username, password = password)
        
        preferences.setValue("jsit", "username", username)
        preferences.setValue("jsit", "password", password)
   
    # Hack...
    mgr._torrentDirectory = os.path.join(basedir, mgr._torrentDirectory)
        
    # For testing...
    ##addIgnoreModule("jsit")
    ##addIgnoreModule("jsit_manager")
    ##addOnlyModule("TorrentTable")
    
    win = JSITWindow(mgr)

    QObject.connect(qapp, SIGNAL("lastWindowClosed()"), win, SLOT("quit()"))
 
    win.show()
    qapp.exec_()
