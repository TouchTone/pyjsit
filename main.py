import operator, copy, os, sys
from PySide.QtCore import *
from PySide.QtGui import *

from log import *
setLogLevel(DEBUG)

import jsitwindow 
import TorrentTable 

import jsit_manager


class JSITWindow(QMainWindow):
    def __init__(self, mgr, *args):
    
        QMainWindow.__init__(self, *args)        
 
        self.mgr = mgr
        
        self.ui = jsitwindow.Ui_JSIT()
        self.ui.setupUi(self)
        
        self.model = TorrentTable.TorrentTableModel(self, mgr)
        self.ui.tableView.setDataModel(self.model)   
    
        # Set up routes to my methods
        self.ui.startB.clicked.connect(self.startAll)
        self.ui.stopB.clicked.connect(self.stopAll)
        
        # Set up update timer
        QTimer.singleShot(0, self.update)
 
    
    def repr(self):
        return "JSITWindow(0x%x)" % id(self)
   
   
    def update(self):
        log(DEBUG, "JSITWindow::update\n")
         
        try:
            self.model.update()
                        
            self.model.updateAttributes(self.ui.tableView)
 
        finally:
            QTimer.singleShot(5000, self.update)

        
    def startAll(self):
        log(DEBUG, "JSITWindow::startAll ")
        
        self.mgr.startAll()        
    
    
    def stopAll(self):
        log(DEBUG, "JSITWindow::stopAll ")
        
        self.mgr.stopAll()        
    



if __name__ == "__main__":
    

    if len(sys.argv) < 3:
        print "Call as %s <username> <password>" % sys.argv[0]
        sys.exit(1)

    mgr = jsit_manager.Manager(username = sys.argv[1], password = sys.argv[2])

    app = QApplication([])
    QObject.connect(app,SIGNAL("lastWindowClosed()"),app,SLOT("quit()"))
     
    win = JSITWindow(mgr)
    win.show()
    app.exec_()
