

// Tool functions

// Based on http://stackoverflow.com/questions/6312993/javascript-seconds-to-time-with-format-hhmmss

function toDDHHMMSS(sec_num) 
{
    var days    = Math.floor(sec_num / 86400);
    var hours   = Math.floor((sec_num % 86400) / 3600);
    var minutes = Math.floor((sec_num %  3600) / 60);
    var seconds = Math.floor( sec_num %  60);

    if (hours   < 10) {hours   = "0"+hours;}
    if (minutes < 10) {minutes = "0"+minutes;}
    if (seconds < 10) {seconds = "0"+seconds;}

    var time;
    if (days == 0)
        time = hours+':'+minutes+':'+seconds;
    else if (days == 1)
        time = days +' day '+hours+':'+minutes+':'+seconds;
    else
        time = days +' days '+hours+':'+minutes+':'+seconds;

    return time;
}

// Visiblity helpers, from http://www.html5rocks.com/en/tutorials/pagevisibility/intro/
function getHiddenProp(){
    var prefixes = ['webkit','moz','ms','o'];

    // if 'hidden' is natively supported just return it
    if ('hidden' in document) return 'hidden';

    // otherwise loop over all the known prefixes until we find one
    for (var i = 0; i < prefixes.length; i++){
        if ((prefixes[i] + 'Hidden') in document) 
            return prefixes[i] + 'Hidden';
    }

    // otherwise it's not supported
    return null;
}

function isHidden() {
    var prop = getHiddenProp();
    if (!prop) return false;

    return document[prop];
}

// From http://stackoverflow.com/questions/387736/how-to-stop-event-propagation-with-inline-onclick-attribute
function disabledEventPropagation(event)
{
    if (event.stopPropagation){
        event.stopPropagation();
    }
    else if(window.event){
        window.event.cancelBubble=true;
    }
}

// Datatables helper functions

function formatTimeDiff(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;

    if (data == 0)
    {
        return "-";
    }

    var p = "";
    if (data < 0)
    {
        p = "-";
        data = -data;
    }

    return p + toDDHHMMSS(data);
}

function formatDate(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;

    if (data == '-')
        return data

    if (data == 0)
    {
        return '<i>unknown</i>';
    }

    d = new Date(data * 1000) 

    return d.toLocaleString();
}

function formatSize(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;

    pref = "";

    if      (data >= 1073741824) { pref = "G"; num = (data / 1073741824).toFixed(2); }
    else if (data >= 1048576)    { pref = "M"; num = (data / 1048576)   .toFixed(2); }
    else if (data >= 1024)       { pref = "K"; num = (data / 1024)      .toFixed(2); }
    else                         {             num =  data              .toFixed(2); }

    return num + " " + pref + "B";
}

function formatBPS(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;

    return formatSize(data, type, row) + "/s"
}

function formatProgress(data, type, row)
{
    if (typeof data == "number")
    {
        pperc = data
            sperc = 100
        text = ""
    }
    else
    {
        var fs = data.split(' / ');
        pperc = fs[0];
        sperc = fs[1];
        text = fs[2];
    }

    if (type == "sort" || type == "type")
        return +pperc;

    if (sperc == 100)
        return '<div id="progress-bar" class="all-rounded"><div id="progress-bar-percentage" class="all-rounded" style="width: ' + pperc + '%"><span>' + pperc + '%</span></div></div>'

    return '<div id="progress-bar" class="all-rounded"><div id="progress-bar-percentage" class="all-rounded" style="width: ' + pperc + '%"><span>' + pperc + '% (' + sperc + '% ' + text + ')</span></div></div>'
}

function formatPriority(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;

    keys = ["10", "30", "50", "70", "90"];
    values = ["Very low", "Low", "Normal", "High", "Very high"];

    for (i=0; i < keys.length; i++)
    {
        if (keys[i] == data)
        {
            return values[i];
        }
    }

    return data;
}


// work functions

var maxLogLines	= 300;	// Number of lines to keep in log.

var selectedTorrents = {}; // Keep track of selected rows to allow updates without losing selection
var lastIdTorrents = undefined; // Last clicked id, for shift-click selection
var selectedDownloads = {};
var lastIdDownloads = undefined;

function filterTorrents(selected, json)
{
    if (json.data[0] == undefined)
    {
        return;
    }

    hi = json.data[0].length - 1;
    known = {};
    for (var i = 0; i < json.data.length; i++)
    {
        known[json.data[i][hi]] = 0;
    }

    for (var i in selected)
    {
        if (! (i in known))
        {
            delete selected[i];
        }
    }

}

function updateTabData()
{
    if (isHidden())
    {
        return
    }

    var active = $( "#tabs" ).tabs( "option", "active" );

    if      (active == 0) { $.getJSON("/updateLog", updateLog ); }
    else if (active == 2) { tabTorrents.ajax.reload(filterTorrents.bind(undefined, selectedTorrents), false); }
    else if (active == 3) { tabChecking.ajax.reload(null, false); }
    else if (active == 4) 
    { 
        tabDownloading.ajax.reload(filterTorrents.bind(undefined, selectedDownloads), false); 
        
        var d = tabDownloading.ajax.json();
        
        var t = "Torrents currently downloading (" + formatSize(d.left, "", "") + " at " + formatBPS(d.speed, "", "");
        if (d.speed > 0)
        {
            t += ", "+ formatTimeDiff(d.left / d.speed ,"", "") + " left" ;
        }
        
        t+= ")";
        
        $("#downloading_title").text(t);
        
    }
    else if (active == 5) { tabFinished.ajax.reload(null, false); }
}

// Timeout management

function timeoutDetected()
{
    if (isHidden())
    {
        return
    }

	var eb = document.getElementById("error_box");	
	eb.style.display = "block";

	self.clearInterval(timeouter);
}

function timeoutReset()
{
	self.clearInterval(timeouter);
    timeouter = self.setInterval(timeoutDetected, 15000);
	var eb = document.getElementById("error_box");	
	eb.style.display = "none";
}

timeouter = self.setInterval(timeoutDetected, 15000);


// Log functions
function updateLog(data)
{
    var div = $("#div_log")[0];

    for (var i = data.length - 1; i >= 0; i--)
    {
        var el = document.createElement("div");
        el.innerHTML = data[i];
        div.insertBefore(el.firstChild, div.firstChild);
    }

    if (div.childNodes.length > maxLogLines)
    {
        while (div.childNodes.length > maxLogLines - 1)
        {
            div.removeChild(div.lastChild);
        }
        var el = document.createElement("span");
        el.innerHTML = "...truncated...";
        div.appendChild(el);
    }
	
	timeoutReset();
}

function getLog()
{
    $.getJSON("/getLog", 
    function( data ) 
    {
        var div = $("#div_log")[0];
    
        for (var i = data.length - 1; i >= 0; i--)
        {
            var el = document.createElement("div");
            el.innerHTML = data[i];
            div.insertBefore(el.firstChild, div.firstChild);
        }
    });
}

function clearLog()
{
    $("#div_log").val("");
    $.get("/clearLog");
}


function addTorrents()
{
    $.get("/addTorrents", { "text" : $("#torrent_links").val() });
    $("#torrent_links").val("");
}


function updateList(event)
{
    $.get('/updateTorrentList')

    setTimeout(updateTabData(), 400);

    disabledEventPropagation(event);
}

function deselectAll()
{
    $("#tab_torrents tr").removeClass("selected");
    selectedTorrents = {};   
    lastIdTorrents = undefined;
    $("#tab_downloading tr").removeClass("selected");
    selectedDownloads = {};   
    selectedIdTorrents = undefined;
}

function filter(event, val)
{
    d = document.getElementById("torrents_filter").value;
    $.get('/setFilter', { "filter" : d } )

    updateTabData();

    event.stopPropagation();
}

function startDownload(event, hash)
{
    $.get('/startDownload', { "hash" : hash })

    disabledEventPropagation(event);
    delete selectedTorrents[hash];

    // Suspend updates for a little bit, to allow starting another download without the UI changing
    self.clearInterval(updater);
    updater = self.setInterval(updateTabData, 2000);
}

function startDownloadAll()
{
    $.get('/startDownloadAll')

    setTimeout(updateTabData(), 400);
}

function startDownloadNonSkipped()
{
    $.get('/startDownloadNonSkipped')

    setTimeout(updateTabData(), 400);
}

function startDownloadSelected()
{
    var d = [];
    for (var i in selectedTorrents)
    {
        d.push(i);
    }

    if ( d.length == 0 )
    {
        var l = tabTorrents.rows()[0];
        var hi = tabTorrents.row(0).data().length - 1;

    for (var i = 0; i < l.length; i++)
    {
        d.push(tabTorrents.row(l[i]).data()[hi]);
    }
}

    for (var i = 0; i < d.length; i++)
    {
        $.get('/startDownload', { "hash": d[i] })
    }

    $("#tab_torrents tr").removeClass("selected");
    selectedTorrents = {};
    setTimeout(updateTabData(), 500);
}


function deleteTorrent(event, hash)
{
    $.get('/delete', { "hash" : hash })

    disabledEventPropagation(event);
    delete selectedTorrents[hash];

    // Suspend updates for a little bit, to allow starting another download without the UI changing
    self.clearInterval(updater);
    updater = self.setInterval(updateTabData, 2000);
}

function deleteSelected()
{
    var d = [];
    for (var i in selectedTorrents)
    {
        d.push(i);
    }

    for (var i = 0; i < d.length; i++)
    {
        $.get('/delete', { "hash": d[i] })
    }

    $("#tab_torrents tr").removeClass("selected");
    selectedTorrents = {};
    setTimeout(updateTabData(), 500);
}


function setLabel()
{
    var e = document.getElementById("select_label");
    var label = e.options[e.selectedIndex].value;
    if (label == '--')
    {
        return;
    }

    var d = [];
    for (var i in selectedTorrents)
    {
        d.push(i);
    }

    if ( d.length == 0 )
    {
        var l = tabTorrents.rows()[0];
        var hi = tabTorrents.row(0).data().length - 1;

    for (var i = 0; i < l.length; i++)
    {
        d.push(tabTorrents.row(l[i]).data()[hi]);
    }
}

    for (var i = 0; i < d.length; i++)
    {
        $.get('/setLabel', { "hash": d[i], "label": label })
    }

    e.selectedIndex = 0;
    setTimeout(updateTabData(), 500);
}


function setPriority(event, elname, active)
{
    var e = document.getElementById(elname);
    var prio = e.options[e.selectedIndex].value;

    if (prio == '--')
    {
        return;
    }

    var selected;
    var tab;

    if (active == 2) { selected = selectedTorrents; tab = tabTorrents; }
    else if (active == 4) { selected = selectedDownloads; tab = tabDownloading; }

    var d = [];
    for (var i in selected)
    {
        d.push(i);
    }

    if ( d.length == 0 )
    {
        var l = tab.rows()[0];
        var hi = tab.row(0).data().length - 1;

    for (var i = 0; i < l.length; i++)
    {
        d.push(tab.row(l[i]).data()[hi]);
    }
}

    for (var i = 0; i < d.length; i++)
    {
        $.get('/setPriority', { "hash": d[i], "prio": prio })
    }

    e.selectedIndex = 0;
    setTimeout(updateTabData(), 500);

    event.stopPropagation();
}

function stopDownload(event, hash)
{
    $.get('/stopDownload', { "hash": hash })

    setTimeout(updateTabData(), 400);

    event.stopPropagation();
}



$(document).ready(function () {

// use the property name to generate the prefixed event name
var visProp = getHiddenProp();
if (visProp) {
    var evtname = visProp.replace(/[H|h]idden/,'') + 'visibilitychange';
    document.addEventListener(evtname, visChange);
}

function visChange() {
    if (! isHidden())
        updateTabData();
}

// Default filter
$.get('/setFilter', { "filter" : "+non-skipped" } )


$( "#tabs" ).tabs({
    heightStyle: "content", 
    active: 0,
    activate: updateTabData
});


tabTorrents = $('#tab_torrents').DataTable( {
    "ajax": "/updateTorrents",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize,     "targets" : 1 },
        { "render": formatProgress, "targets" : 2 },
        { "render": formatPriority, "targets" : 4 },
        { "render": formatBPS,      "targets" : 5 },
        { "render": formatTimeDiff, "targets" : 6 },
        { "render": formatTimeDiff, "targets" : 7 }
    ],
    "columns" : [
        { className: "aLeft" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aCenter" },
        { className: "aCenter" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aCenter" }
    ],
    "createdRow": function ( row, data, index ) 
    {
        row.id = data[data.length - 1];
        if ( row.id in selectedTorrents ) 
        {
            row.classList.add('selected');
        }
    }
} );

tabTorrents.on('xhr.dt', timeoutReset);

$("#tab_torrents_wrapper").click(function(e) {
    e.stopPropagation();
})

    $('#tab_torrents tbody').on( 'click', 'tr', function (event) 
    {            
        var id = this.id;
        var set;

    $(this).toggleClass('selected');
    if ($(this).hasClass('selected'))
    {
        selectedTorrents[id] = 0;
        set = true;
    }
    else
    {
        delete selectedTorrents[id];
        set = false;
    }

    if (event.shiftKey)
    {
        var inside = false;

    tabTorrents.rows({search:'applied'}).indexes().each( function (idx) 
    {
        var d = tabTorrents.row( idx ).data();
        var iid = d[d.length-1];

    if (inside)
    {
        tr = $("#" + iid);

    tr.toggleClass('selected', set);
    if (tr.hasClass('selected'))
    {
        selectedTorrents[iid] = 0;
    }
    else
    {
        delete selectedTorrents[iid];
    }                  
}

    if (iid == lastIdTorrents || iid == id)
    {   
        inside = !inside;
    }
});
document.getSelection().removeAllRanges();
}

    lastIdTorrents = id;
    disabledEventPropagation(event);
} );


tabChecking = $('#tab_checking').DataTable( {
    "ajax": "/updateChecking",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize, "targets" : 1 },
        { "render": formatProgress, "targets" : 2 }
    ],
    "columns" : [
        { className: "aLeft" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aCenter" }
    ],
    "order": [[ 2, "desc" ]]
} );

tabChecking.on('xhr.dt', timeoutReset);

tabDownloading = $('#tab_downloading').DataTable( {
    "ajax": "/updateDownloading",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize,     "targets" : 1 },
        { "render": formatProgress, "targets" : 2 },
        { "render": formatPriority, "targets" : 3 },
        { "render": formatBPS,      "targets" : 4 },
        { "render": formatTimeDiff, "targets" : 5 },
        { "render": formatTimeDiff, "targets" : 6 }
    ],
    "columns" : [
        { className: "aLeft" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aCenter" },
        { className: "aRight" },
        { className: "aRight" },
        { className: "aCenter" }
    ],
    "order": [[ 2, "desc" ]],
    "createdRow": function ( row, data, index ) 
    {
        row.id = data[data.length - 1];
        if ( row.id in selectedDownloads ) 
        {
            row.classList.add('selected');
        }
    }
} );

tabDownloading.on('xhr.dt', timeoutReset);

$("#tab_downloading_wrapper").click(function(e) {
    e.stopPropagation();
})

    $('#tab_downloading tbody').on( 'click', 'tr', function (event) {        
        var id = this.id;
        var set;

    $(this).toggleClass('selected');
    if ($(this).hasClass('selected'))
    {
        selectedDownloads[id] = 0;
        set = true;
    }
    else
    {
        delete selectedDownloads[id];
        set = false;
    }

    if (event.shiftKey)
    {
        var inside = false;

    tabDownloading.rows({search:'applied'}).indexes().each( function (idx) 
    {
        var d = tabDownloading.row( idx ).data();
        var iid = d[d.length-1];

    if (inside)
    {
        tr = $("#" + iid);

    tr.toggleClass('selected', set);
    if (tr.hasClass('selected'))
    {
        selectedDownloads[iid] = 0;
    }
    else
    {
        delete selectedDownloads[iid];
    }                  
}

    if (iid == lastIdDownloads || iid == id)
    {   
        inside = !inside;
    }
});
document.getSelection().removeAllRanges();
}

    lastIdDownloads = id;
    disabledEventPropagation(event);
} );


tabFinished = $('#tab_finished').DataTable( {
    "ajax": "/updateFinished",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize, "targets" : 1 },
        { "render": formatDate, "targets" : 3 }
    ],
    "columns" : [
        { className: "aLeftt" },
        { className: "aRight" },
        { className: "aCenter" },
        { className: "aRight" },
        { className: "aCenter" }
    ],
    "order": [[ 3, "desc" ]]
} );

tabFinished.on('xhr.dt', timeoutReset);


updater = self.setInterval(updateTabData, {updateRate});

getLog();

});
