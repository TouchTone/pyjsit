import operator, copy, datetime
from PySide.QtCore import *
from PySide.QtGui import *

import jsit_manager
from log import *


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
         
 
class ProgressBarDelegate(QStyledItemDelegate):

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)


    def paint(self, painter, option, index):   
       
        item_var = index.data(Qt.DisplayRole)
        ##print "PBD: %s = %s" % (index, item_var)

        opts = QStyleOptionProgressBar()
        opts.rect = option.rect
        opts.minimum = 0
        opts.maximum = 100
        opts.text = str(item_var)
        opts.textAlignment = Qt.AlignCenter
        opts.textVisible = True
        opts.progress = int(item_var)
        QApplication.style().drawControl(QStyle.CE_ProgressBar, opts,painter)




class TorrentSortFilterProxyModel(QSortFilterProxyModel):

    def lessThan(self, left_index, right_index):
    
        left_var = left_index.data(Qt.DisplayRole)
        right_var = right_index.data(Qt.DisplayRole)

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


      
       
class TorrentTableView(QTableView):
    def __init__(self, parent = None):
        super(TorrentTableView, self).__init__(parent)
 
    
    def repr(self):
        return "TorrentTableView(0x%x)" % id(self)


    def setDataModel(self, table_model): 
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
       
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

        ## uniform one for the horizontal headers.to select columns
        self.horizontalHeader().setContextMenuPolicy(Qt.ActionsContextMenu)

        for i,n in enumerate(table_model.header):
            a = QAction("&" + table_model.header[i].strip(), self.horizontalHeader(),
                              triggered = lambda i=i: self.flipColumn(i), checkable = True, checked = True)
            self.horizontalHeader().addAction(a)       
            
            if table_model.delegate(i):
                self.setItemDelegateForColumn(i, table_model.delegate(i)(self))
 
        return


    def flipColumn(self, index):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        if self.isColumnHidden(index):
            #print "flipColumn: turning %d on" % index
            self.setColumnHidden(index, False)
        else:
            #print "flipColumn: turning %d off" % index
            self.setColumnHidden(index, True)
        self.emit(SIGNAL("layoutChanged()"))
        

    def trig1(self, *args, **kwargs):
        print "TRIG1",args, kwargs
        sm = self.selectionModel()
        print sm.hasSelection()
        for r in sm.selectedRows():
            print r.row()
        
        
    
    # Generic context menu
    
    def contextMenuEvent(self, event):
        ''' The super function that can handle each cell as you want it'''
        handled = False
        index = self.indexAt(event.pos())
        menu = QMenu()
        
        
        #an action for everyone
        
        
        every = QAction("I'm for everyone", menu, triggered = self.trig1)
        if index.column() == 0:  #treat the Nth column special row...
            #action_1 = QAction("Something Awesome", menu,
            #                   triggered = self.trig2 )
            #action_2 = QAction("Something Else Awesome", menu,
            #                   triggered = self.trig3 )
            #menu.addActions([action_1, action_2])
            handled = True
        #elif index.column() == SOME_OTHER_SPECIAL_COLUMN:
            #action_1 = QAction("Uh Oh", menu, triggered = YET_ANOTHER_FUNCTION)
            #menu.addActions([action_1]
            handled = True
            #pass

        if handled:
            menu.addAction(every)
            menu.exec_(event.globalPos())
            event.accept() #TELL QT IVE HANDLED THIS THING

        else:
            event.ignore() #GIVE SOMEONE ELSE A CHANCE TO HANDLE IT

        return



# Data Model

ag = operator.attrgetter

# Access the underlying variable, not the property methods, to avoid stalling on updates.
# The actual values are updated in updateAttributes
def tg(field):
    return lambda t, field=field: operator.attrgetter("_" + field)(t._torrent)
 
def dg(field):
    return lambda t, field=field: t._aria and getattr(t._aria, field)
   
# Data mappers

def isoize(val, unit):
    num=float(val)
    sizes = ["", "K", "M", "G", "T"]
    for s in sizes:
        if num < 1024:
            sn = "%.2f %s" % (num, s)
            break
        num /= 1024.0
    return sn + unit

isoize_b = lambda v: isoize(v, "B")
isoize_bps = lambda v: isoize(v, "B/s")


# Based on http://stackoverflow.com/questions/538666/python-format-timedelta-to-string
def printNiceTimeDelta(delta):
    delay = datetime.timedelta(seconds=int(delta))
    if (delay.days > 0):
        out = str(delay).replace(" days, ", ":")
    else:
        out = "0:" + str(delay)
    outAr = out.split(':')
    outAr = ["%02d" % (int(float(x))) for x in outAr]
    out   = ":".join(outAr)
    return out    
    


torrent_colums = [  { "name":"Name",             "acc":ag, "vname":"name" },
                    { "name":"Size",             "acc":ag, "vname":"size",           "map":isoize_b, "align":Qt.AlignCenter}, # Qt.AlignCenter|Qt.AlignRight doesn't work
                    { "name":"Percentage",       "acc":ag, "vname":"percentage",     "deleg":ProgressBarDelegate},
                    { "name":"Label",            "acc":ag, "vname":"label"},
                    
                    { "name":"Downloaded",       "acc":tg, "vname":"downloaded",     "map":isoize_b},
                    { "name":"Uploaded",         "acc":tg, "vname":"uploaded",       "map":isoize_b},
                    { "name":"Data Rate In",     "acc":tg, "vname":"data_rate_in",   "map":isoize_bps},
                    { "name":"Data Rate Out",    "acc":tg, "vname":"data_rate_out",  "map":isoize_bps},
                    { "name":"Elapsed",          "acc":tg, "vname":"elapsed",        "map":printNiceTimeDelta},
                    { "name":"Status",           "acc":tg, "vname":"status"},
                    { "name":"TPercentage",      "acc":tg, "vname":"percentage",     "deleg":ProgressBarDelegate}
                   
                    { "name":"DPercentage",      "acc":dg, "vname":"percentage",     "deleg":ProgressBarDelegate}
                 ]


class TorrentTableModel(QAbstractTableModel):
    def __init__(self, parent, mgr, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        
        self.mgr = mgr
        self.hashes = [ t.hash for t in mgr ]
        
        self.header = [ e["name"] for e in torrent_colums ]
 
    
    def repr(self):
        return "TorrentTableModel(0x%x)" % id(self)

    
    def delegate(self, index):
        try:
            return torrent_colums[index]["deleg"]
        except KeyError:
            return None
    
    
    def hasChildren(self, parent):
        if parent and not parent.isValid():
            log(DEBUG, "yes\n")
            return True
        else:
            log(DEBUG, "no\n")
            return False
    
    
    def parent(self, child):
        log(DEBUG)
        return QModelIndex()
        
        
    def rowCount(self, parent):
        if parent and not parent.isValid():
            log(DEBUG2, "row count=%d\n" % len(self.mgr))
            return len(self.mgr)
        else:
            return 0
        
        
    def columnCount(self, parent):
        if parent and not parent.isValid():
            log(DEBUG2, "column count=%d\n" % len(torrent_colums))
            return len(torrent_colums)
        else:
            return 0
        
        
    def data(self, index, role):
        if not index.isValid():
            return None

        tc = torrent_colums[index.column()]
            
        if role == Qt.TextAlignmentRole:
            try:
                return tc["align"]
            except KeyError:
                return None
                
        elif role != Qt.DisplayRole:
            return None
            
        v = tc["acc"](tc["vname"])(self.mgr[index.row()])

        try:
            v = tc["map"](v)
        except KeyError:
            pass
        
        log(DEBUG2, "v=%s\n" % v)
        
        return v
        
        
    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None
        

    def updateAttributes(self, view):
        '''Update attribute values that are used in table'''
        
        log(DEBUG, "TorrentTableModel::updateAttributes\n")
        
        for i,v in enumerate(torrent_colums):
        
            # Ignore hidden columns and attribs not from torrent
            if view.isColumnHidden(i) or v["acc"] != tg:
                continue

            for t in self.mgr:
                # Just access it to update, don't need to do anything with it
                operator.attrgetter(v["vname"])(t._torrent)

                # Process events just in case this takes a long time
                QApplication.processEvents()


    def update(self):
            new, deleted = self.mgr.update()
            
            #self.reset()
            #return
            
            if len(new) != 0 or len(deleted) != 0:

                self.emit(SIGNAL("LayoutAboutToBeChanged()")) 

                if len(deleted) != 0:                    
                    for d in deleted:
                        ind = self.hashes.index(d)
                        self.beginRemoveRows(QModelIndex(), ind, ind)
                        ret = self.removeRow(ind)
                        self.endRemoveRows()
                        
                        log(DEBUG, "del: hash %s -> ind=%d : %s\n" % (d, ind, ret))


                if len(new) != 0:                    
                    for n in new:
                        ind = len(self.hashes)
                        self.beginInsertRows(QModelIndex(), ind, ind)
                        self.hashes.append(n)                       
                        ret = self.insertRow(ind)
                        self.endInsertRows()
                        
                        log(DEBUG, "new: hash %s -> ind=%d : %s\n" % (n, ind, ret))

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
