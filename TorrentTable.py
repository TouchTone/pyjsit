import operator, copy, datetime
from PySide.QtCore import *
from PySide.QtGui import *

from preferences import pref
import jsit_manager
from log import *
from tools import *

# Delegate to draw a graph in a cell (test version)

class DrawGraphDelegate(QStyledItemDelegate):

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)


    def paint(self, painter, option, index):   
        ##QStyledItemDelegate.paint(self, painter, option, index)
        
        item_var = index.data(Qt.DisplayRole)
        
        painter.save()
        
        baseHue = 0.4
        
        baseColor = QColor()
        baseColor.setHsvF(baseHue, 0.2, 1.)
        
        lineColor = QColor()
        lineColor.setHsvF(baseHue, 0.8, 1.)
        
        borderColor = QColor()
        borderColor.setHsvF(baseHue, 0.4, 1.)

        painter.setRenderHint(QPainter.Antialiasing, True)
        
        r = option.rect.adjusted(2,2,-2,-2)
        painter.setBrush(QBrush(baseColor))
        painter.drawRoundedRect(r, 2, 2)
         
        painter.setPen(lineColor)
        pts = [ QPointF(r.left(),r.bottom()), r.center(),QPointF(r.right(),r.bottom()) ]
        painter.drawPolyline(pts)
        
        to = QTextOption()
        to.setAlignment(Qt.AlignRight | Qt.AlignTop)
        font = QFont("Sans", 8)
        painter.setFont(font)
        
        painter.drawText(r, str(item_var) + " kb/s", to)
       
        painter.restore()
         
 
# Delegate to draw a progress bar in a cell with values from 0 to 100

class ProgressBarDelegate(QStyledItemDelegate):

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)


    def paint(self, painter, option, index):   
       
        item_var = index.data(Qt.DisplayRole)
        
        if item_var == None:
            return

        opts = QStyleOptionProgressBar()
        opts.rect = option.rect
        opts.minimum = 0
        opts.maximum = 100
        opts.text = "{:.1%}".format(float(item_var) / 100.)
        opts.textAlignment = Qt.AlignCenter
        opts.textVisible = True
        opts.progress = int(item_var)
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opts, painter)


# Delegate to draw checkboxes for boolean values (editable if model says so)
# From http://stackoverflow.com/questions/3363190/qt-qtableview-how-to-have-a-checkbox-only-column

class CheckBoxDelegate(QStyledItemDelegate):

    def createEditor(self, parent, option, index):
        '''
        Important, otherwise an editor is created if the user clicks in this cell.
        '''
        return None

    def paint(self, painter, option, index):
        '''
        Paint a checkbox without the label.
        '''
        checked = bool(index.model().data(index, Qt.DisplayRole))
        check_box_style_option = QStyleOptionButton()

        if (index.flags() & Qt.ItemIsEditable) > 0:
            check_box_style_option.state |= QStyle.State_Enabled
        else:
            check_box_style_option.state |= QStyle.State_ReadOnly

        if checked:
            check_box_style_option.state |= QStyle.State_On
        else:
            check_box_style_option.state |= QStyle.State_Off

        check_box_style_option.rect = self.getCheckBoxRect(option)
        #if not index.model().hasFlag(index, Qt.ItemIsEditable):
        #    check_box_style_option.state |= QStyle.State_ReadOnly

        QApplication.style().drawControl(QStyle.CE_CheckBox, check_box_style_option, painter)


    def editorEvent(self, event, model, option, index):
        '''
        Change the data in the model and the state of the checkbox
        if the user presses the left mousebutton or presses
        Key_Space or Key_Select and this cell is editable. Otherwise do nothing.
        '''
        if not (index.flags() & Qt.ItemIsEditable) > 0:
            return False

        # Do not change the checkbox-state
        if event.type() == QEvent.MouseButtonRelease or event.type() == QEvent.MouseButtonDblClick:
            if event.button() != Qt.LeftButton or not self.getCheckBoxRect(option).contains(event.pos()):
                return False
            if event.type() == QEvent.MouseButtonDblClick:
                return True
        elif event.type() == QEvent.KeyPress:
            if event.key() != Qt.Key_Space and event.key() != Qt.Key_Select:
                return False
        else:
            return False

        # Change the checkbox-state
        self.setModelData(None, model, index)
        return True

    def setModelData (self, editor, model, index):
        '''
        The user wanted to change the old state in the opposite.
        '''
        newValue = not bool(index.model().data(index, Qt.DisplayRole))
        model.setData(index, newValue, Qt.EditRole)


    def getCheckBoxRect(self, option):
        check_box_style_option = QStyleOptionButton()
        check_box_rect = QApplication.style().subElementRect(QStyle.SE_CheckBoxIndicator, check_box_style_option, None)
        check_box_point = QPoint (option.rect.x() +
                             option.rect.width() / 2 -
                             check_box_rect.width() / 2,
                             option.rect.y() +
                             option.rect.height() / 2 -
                             check_box_rect.height() / 2)
        return QRect(check_box_point, check_box_rect.size())


# Directory Selection Box Delegate
# Thanks to http://stackoverflow.com/questions/22868856/qfiledialog-as-editor-for-tableview-how-to-get-result

class DirectorySelectionDelegate(QStyledItemDelegate):

    def createEditor(self, parent, option, index):
    
        log(DEBUG)
        editor = QFileDialog(parent)
        editor.setFileMode(QFileDialog.Directory)       
        editor.setOption(QFileDialog.ShowDirsOnly, True)    
        editor.setModal(True)
        editor.filesSelected.connect( lambda: editor.setResult(QDialog.Accepted))
        index.model().startEditing()
        
        log(DEBUG, "Editor=%s\n" % editor)
        
        return editor


    def setEditorData(self, editor, index):
        val = index.model().data(index, Qt.DisplayRole)
        log(DEBUG, "val=%r\n" % val)
        fs = val.rsplit(os.path.sep, 1)
        if len(fs) == 2:
            bdir, vdir = fs
        else:
            bdir = "."
            vdir = fs[0]
            
        editor.setDirectory(bdir)        
        editor.selectFile(vdir)        
        

    def setModelData(self, editor, model, index):
        if editor.result() == QDialog.Accepted:
            model.setData(index, editor.selectedFiles()[0])
        
        model.stopEditing()


    def updateEditorGeometry(self, editor, option, index):
        log(DEBUG)
        
        r = option.rect
        r.setHeight(600)
        r.setWidth(600)
        
        editor.setGeometry(r)
        
        
        
# Sort/filter proxy. Mainly sort. ;)

class TorrentSortFilterProxyModel(QSortFilterProxyModel):

    def lessThan(self, left_index, right_index):
    
        left_var = left_index.data(Qt.EditRole)
        right_var = right_index.data(Qt.EditRole)

        try:
            return float(left_var) < float(right_var)
        except (ValueError, TypeError):
            pass
        return left_var < right_var
    
    
    def filterAcceptsRowQQQ(self, src_row, src_parent):
        src_model = self.sourceModel()
        src_index = src_model.index(src_row, 2)
        
        item_var = src_index.data(Qt.DisplayRole)
        
        return (item_var >= 0)

    # Forward some needed extensions
    
    def startEditing(self):
        log(DEBUG)
        self.sourceModel().startEditing()
    
    def stopEditing(self):
        log(DEBUG)
        self.sourceModel().stopEditing()


###################################################################
# The main view class for the torrent list     
       
class TorrentTableView(QTableView):
    def __init__(self, parent = None):
        super(TorrentTableView, self).__init__(parent)
 
    
    def __repr__(self):
        return "TorrentTableView(0x%x)" % id(self)


    def setDataModel(self, table_model): 
    
        self._model = table_model
        
        proxy = TorrentSortFilterProxyModel()
        proxy.setSourceModel(table_model)
        proxy.sort(0)
        
        self.setModel(proxy)
        
        # set font
        font = QFont("Sans", 12)
        self.setFont(font)
        
        # set column width to fit contents (set font first!)
        self.resizeColumnsToContents()
        
        # enable sorting
        self.setSortingEnabled(True)
        proxy.setDynamicSortFilter(True)

        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        hh = self.horizontalHeader()
        hh.setMovable(True)

        ## uniform menu for the horizontal headers.to select columns
        self.horizontalHeader().setContextMenuPolicy(Qt.ActionsContextMenu)

        for i,n in enumerate(table_model.header):
            a = QAction("&" + table_model.header[i].strip(), self.horizontalHeader(),
                              triggered = lambda i=i: self.flipColumn(i), checkable = True, checked = True)
            self.horizontalHeader().addAction(a)       
            
            if pref("GUI", "hidecol_" + n):
                self.setColumnHidden(i, True)
            
            if table_model.delegate(i):
                self.setItemDelegateForColumn(i, table_model.delegate(i)(self))
        
        # Specific one for the actual table
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

        return


    # Turning columns on/off 
    
    def flipColumn(self, index):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        if self.isColumnHidden(index):
            log(DEBUG, "turning %d on\n" % index)
            self.setColumnHidden(index, False)
        else:
            log(DEBUG, "turning %d off\n" % index)
            self.setColumnHidden(index, True)
        self.emit(SIGNAL("layoutChanged()"))
        
        
    # Torrent Actions        
    
    def startTorrent(self):
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.start()
            
        self._model.mgr


    def stopTorrent(self):
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))
            tor.stop()


    def deleteTorrent(self):
        sm = self.selectionModel()
    
        msg = "This will delete the following torrents and their data from justseed.it:\n\n"
        
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            msg += "%s\n" % tor.name

        msg += "\nAre you sure?"
        
        msgBox = QMessageBox()
        msgBox.setText("Deleting Torrents")
        msgBox.setInformativeText(msg)
        msgBox.setStandardButtons(QMessageBox.Cancel | QMessageBox.Apply)
        msgBox.setDefaultButton(QMessageBox.Cancel)
        ret = msgBox.exec_()

        if ret == QMessageBox.Apply:
            for r in sm.selectedRows():
                ri = self.model().mapToSource(r)
                tor = self._model.mgr[ri.row()]

                log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))
                tor.delete()


    def startDownload(self):
        log(INFO)
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.startDownload()


    def restartDownload(self):
        log(INFO)
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.restartDownload()
    

    def recheckDownload(self):
        log(INFO)
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.recheckDownload()


    def changeLabel(self):
        log(INFO)
        
        labels = self._model.mgr._jsit.labels
        
        label, ok = QInputDialog.getItem(self, "Set Label...", "Choose label:", ["<None>"] + labels)
        
        if not ok:
            log(INFO, "Aborted.\n")
            return
        
        if label == "<None>":
            label = None
            
        log(INFO, "Picked %s.\n" % label)
        
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.label = label
    
        # Entered a new label? Update list...
        if label and not label in labels:
            self._model.mgr._jsit.updateLabels(force=True)


    def changeDownloadDir(self):
        log(INFO)
        
        basedir = None
        
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            if basedir == None:
                basedir = tor.basedir
            elif basedir != tor.basedir:
                basedir = None
                break
        
        
        editor = QFileDialog(self)
        editor.setFileMode(QFileDialog.Directory)       
        editor.setModal(True)
        editor.setOption(QFileDialog.ShowDirsOnly, True)    
         
        if basedir:        
            fs = basedir.rsplit(os.path.sep, 1)
            if len(fs) == 2:
                bdir, vdir = fs
            else:
                bdir = "."
                vdir = fs[0]

            editor.setDirectory(bdir)        
            editor.selectFile(vdir)        
        
        ok = editor.exec_()
               
        if not ok:
            log(INFO, "Aborted.\n")
            return
            
        bd = editor.selectedFiles()[0]
        
        log(INFO, "Picked %s.\n" % bd)
        
        sm = self.selectionModel()
        for r in sm.selectedRows():
            ri = self.model().mapToSource(r)
            tor = self._model.mgr[ri.row()]
            
            log(DEBUG, "%d (%d): %s\n"% (ri.row(), r.row(),tor))

            tor.basedir = bd
             
    
    # Generic context menu
    
    def contextMenuEvent(self, event):
        ''' The super function that can handle each cell as you want it'''
        handled = False
        
        index = self.indexAt(event.pos())
        ri = self.model().mapToSource(index)
        tor = self._model.mgr[ri.row()]
        col = index.column();
        
        menu = QMenu()

        # General actions
        
        menu.addAction(QAction("Start", menu, triggered = self.startTorrent))
        menu.addAction(QAction("Stop", menu, triggered = self.stopTorrent))
        menu.addAction(QAction("Delete", menu, triggered = self.deleteTorrent))
        menu.addSeparator()
        
        fas = []
        fas.append(QAction("Start Download", menu, triggered = self.startDownload))
        ## NIY fas.append(QAction("Restart Download", menu, triggered = self.restartDownload))
        if not tor._torrent.hasFinished:
            for f in fas:
                f.setEnabled(False)
        for f in fas:        
            menu.addAction(f)
        menu.addSeparator()

        menu.addAction(QAction("Change Label", menu, triggered = self.changeLabel))
        menu.addAction(QAction("Change Download Dir", menu, triggered = self.changeDownloadDir))
            
        ## Not finished yet... menu.addAction(QAction("Recheck Downloaded", menu, triggered = self.recheckDownload))
         
        #if index.column() == 0:  #treat the Nth column special row...
            #action_1 = QAction("Something Awesome", menu,
            #                   triggered = self.trig2 )
            #action_2 = QAction("Something Else Awesome", menu,
            #                   triggered = self.trig3 )
            #menu.addActions([action_1, action_2])
        #    handled = True
        #elif index.column() == SOME_OTHER_SPECIAL_COLUMN:
            #action_1 = QAction("Uh Oh", menu, triggered = YET_ANOTHER_FUNCTION)
            #menu.addActions([action_1]

        handled = True

        if handled:
            menu.exec_(event.globalPos())
            event.accept() #TELL QT IVE HANDLED THIS THING

        else:
            event.ignore() #GIVE SOMEONE ELSE A CHANCE TO HANDLE IT

        return


###################################################################
# Data Model

# Access helpers

def aget(tor, field):
    return getattr(tor, field)

def aset(tor, field, newval):
    return setattr(tor, field, newval)

# Access the underlying variable, not the property methods, to avoid stalling on updates.
# The actual values are updated in updateAttributes
def tget(tor, field):
    return getattr(tor._torrent, "_" + field)
 
def dget(tor, field):
    if not tor._aria:
        return 0
    return getattr(tor._aria, field)
   
   
# Data mappers

torrent_colums = [  
    { "name":"Name",             "acc":aget, "vname":"name", "align":0x81 },
    { "name":"Size",             "acc":aget, "vname":"size",           "map":isoize_b},
    { "name":"Percentage",       "acc":aget, "vname":"percentage",     "deleg":ProgressBarDelegate},
    { "name":"Label",            "acc":aget, "vname":"label", "align":0x84},
    { "name":"Download\nWhen finished",         "acc":aget, "vname":"autoStartDownload", "deleg":CheckBoxDelegate, "setter":aset},
    { "name":"Base Directory",   "acc":aget, "vname":"basedir", "align":0x84,        "deleg":DirectorySelectionDelegate, "setter":aset},
    
    { "name":"Torrent\nDownloaded",       "acc":tget, "vname":"downloaded",     "map":isoize_b},
    { "name":"Torrent\nUploaded",         "acc":tget, "vname":"uploaded",       "map":isoize_b},
    { "name":"Torrent\nRatio",         "acc":tget, "vname":"ratio",       "map":lambda v:"{:.02f}".format(v)},
    { "name":"Maximum\nRatio",         "acc":tget, "vname":"maximum_ratio",       "map":lambda v:"{:.02f}".format(v)},
    { "name":"Torrent\nData Rate In",     "acc":tget, "vname":"data_rate_in",   "map":isoize_bps},
    { "name":"Torrent\nData Rate Out",    "acc":tget, "vname":"data_rate_out",  "map":isoize_bps},
    { "name":"Status",           "acc":tget, "vname":"status"},
    { "name":"Torrent\nPercentage",      "acc":tget, "vname":"percentage",     "deleg":ProgressBarDelegate},
   
    { "name":"Local\nPercentage",      "acc":dget, "vname":"percentage",     "deleg":ProgressBarDelegate},
    { "name":"Local\nDownloaded",       "acc":dget, "vname":"downloaded",     "map":isoize_b},
    { "name":"Local\nDownload Speed",   "acc":dget, "vname":"downloadSpeed",  "map":isoize_bps},
    { "name":"Files Pending",    "acc":dget, "vname":"filesPending"}
]


class TorrentTableModel(QAbstractTableModel):
    def __init__(self, parent, mgr, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        
        self.mgr = mgr
        self.hashes = [ t.hash for t in mgr ]
        
        self.header = [ e["name"] for e in torrent_colums ]
 
        self.editing = 0    # If editor is open, don't update table, as that resets editor
        
    
    def __repr__(self):
        return "TorrentTableModel(0x%x)" % id(self)


    def startEditing(self):
        self.editing += 1
 
    def stopEditing(self):
        self.editing -= 1
       
    
    def delegate(self, index):
        try:
            return torrent_colums[index]["deleg"]
        except KeyError:
            return None
    
    
    def hasChildren(self, parent):
        if parent and not parent.isValid():
            log(DEBUG3, "yes\n")
            return True
        else:
            log(DEBUG3, "no\n")
            return False
    
    
    def parent(self, child):
        log(DEBUG3)
        return QModelIndex()
        
        
    def rowCount(self, parent):
        if parent and not parent.isValid():
            log(DEBUG3, "row count=%d\n" % len(self.mgr))
            return len(self.mgr)
        else:
            return 0
        
        
    def columnCount(self, parent):
        if parent and not parent.isValid():
            log(DEBUG3, "column count=%d\n" % len(torrent_colums))
            return len(torrent_colums)
        else:
            return 0


    def flags(self, index):
        if not index.isValid():
            return None

        tc = torrent_colums[index.column()]
    
        if tc.has_key("setter"):        
            return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable 
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable    
        
        
    def data(self, index, role):
        if not index.isValid():
            return None

        tc = torrent_colums[index.column()]
            
        if role == Qt.TextAlignmentRole:
            try:
                return tc["align"]
            except KeyError:
                return 0x82 # Qt.AlignRight | Qt.AlignVCenter doesn't work
                
        if role == Qt.DisplayRole or role == Qt.EditRole:
            v = tc["acc"](self.mgr[index.row()], tc["vname"])

            if role == Qt.DisplayRole:
                try:
                    v = tc["map"](v)
                except KeyError:
                    pass

            log(DEBUG2, "v=%s\n" % v)

            return v
        
        return None
        
        
    def setData(self, index, newval, role):
        if not index.isValid():
            return False
            
        if role != Qt.EditRole:
            return False

        tc = torrent_colums[index.column()]
        
        try:
            tc["setter"](self.mgr[index.row()], tc["vname"], newval)
        except KeyError:
            log(DEBUG, "newval=%s failed\n" % newval)
            return False
                    
        log(DEBUG, "newval=%s success\n" % newval)       
        return True
        
        
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None
        

    def updateAttributes(self, view):
        '''Update attribute values that are used in table'''

        if self.editing:
            log(DEBUG, "editing, canceled\n")
            return
        
        log(DEBUG)
        
        for i,v in enumerate(torrent_colums):
        
            # Ignore hidden columns and attribs not from torrent
            if view.isColumnHidden(i) or v["acc"] != tget:
                continue

            for t in self.mgr:
                # Just access it to update, don't need to do anything with it
                operator.attrgetter(v["vname"])(t._torrent)

                # Process events just in case this takes a long time
                QApplication.processEvents()


    def update(self, clip = None):
        log(DEBUG)
        new, deleted = self.mgr.update(clip = clip)

        if self.editing:
            log(DEBUG, "editing, canceled\n")
            return

        if len(new) != 0 or len(deleted) != 0:

            self.emit(SIGNAL("LayoutAboutToBeChanged()")) 

            if len(deleted) != 0:                    
                for d in deleted:
                    ind = self.hashes.index(d)
                    self.beginRemoveRows(QModelIndex(), ind, ind)
                    ret = self.removeRow(ind)
                    self.endRemoveRows()

                    log(INFO, "del: hash %s -> ind=%d : %s\n" % (d, ind, ret))


            if len(new) != 0:                    
                for n in new:
                    ind = len(self.hashes)
                    self.beginInsertRows(QModelIndex(), ind, ind)
                    self.hashes.append(n)                       
                    ret = self.insertRow(ind)
                    self.endInsertRows()

                    log(INFO, "new: hash %s -> ind=%d : %s\n" % (n, ind, ret))

            self.emit(SIGNAL("LayoutChanged()")) 

        i0 = self.createIndex(0, 0)
        im = self.createIndex(self.rowCount(0), self.columnCount(0))

        self.dataChanged.emit(i0, im) 
        self.emit(SIGNAL("DataChanged(QModelIndex,QModelIndex)"), i0, im)
                         

if __name__ == "__main__":

    from modeltest import ModelTest
    import sys

    import jsit_manager, main, TorrentTable
    
    if len(sys.argv) < 3:
        print "Call as %s <username> <password>" % sys.argv[0]
        sys.exit(1)

    mgr = jsit_manager.Manager(username = sys.argv[1], password = sys.argv[2])

    app = QApplication([])
    win = main.JSITWindow(mgr)
    
    model = TorrentTable.TorrentTableModel(win, mgr)
    
    modeltest = ModelTest(model, None)
