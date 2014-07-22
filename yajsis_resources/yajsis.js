

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
    else                         { num = data; }
    
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
    if (type == "sort" || type == "type")
        return +data;
    
    //return "<progress value='" + data + "' max='100'>" + data + "</progress>";
    return '<div id="progress-bar" class="all-rounded"><div id="progress-bar-percentage" class="all-rounded" style="width: ' + data + '%"><span>' + data + '%</span></div></div>'
}


// work functions

var nSelected = 0; // Suspend updates for torrent tab if rows are selected

function updateTabData()
{
    if (isHidden())
    {
        return
    }
    
    var active = $( "#tabs" ).tabs( "option", "active" );
    
    if      (active == 0) { $.getJSON("/updateLog", function( data ) { $("#div_log").append(data); } ); }
    else if (active == 2 && nSelected == 0) { tabTorrents.ajax.reload(null, false); }
    else if (active == 3) { tabChecking.ajax.reload(null, false); }
    else if (active == 4) { tabDownloading.ajax.reload(null, false); }
    else if (active == 5) { tabFinished.ajax.reload(null, false); }
    
}

function getLog()
{
    $.getJSON("/getLog", 
    function( data ) {
        $("#div_log").html(data);
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


function updateList(hash)
{
    $.get('/updateTorrentList')
    
    setTimeout(updateTabData(), 400);
}

function startDownload(hash)
{
    $.get('/startDownload', { "hash": hash })
    
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
    var d = tabTorrents.rows('.selected')[0];
    var hi = tabTorrents.row(0).data().length - 1;
    
    for (var i = 0; i < d.length; i++)
    {
        $.get('/startDownload', { "hash": tabTorrents.row(d[i]).data()[hi] })
    }
    
    $("#tab_torrents tr").removeClass("selected");
    nSelected = 0;
    setTimeout(updateTabData(), 500);
}

function stopDownload(hash)
{
    $.get('/stopDownload', { "hash": hash })
    
    setTimeout(updateTabData(), 400);
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
        { "render": formatBPS,      "targets" : 4 },
        { "render": formatTimeDiff, "targets" : 5 },
        { "render": formatTimeDiff, "targets" : 6 }
    ],
    "columns" : [
        {  className: "aLeft" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" }
    ]
} );

 $('#tab_torrents tbody').on( 'click', 'tr', function () {
        $(this).toggleClass('selected');
        if ($(this).hasClass('selected'))
        {
            nSelected += 1;
        }
        else
        {
            nSelected -= 1;
        }
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
        {  className: "aLeft" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" }
    ],
    "order": [[ 2, "desc" ]]
} );

tabDownloading = $('#tab_downloading').DataTable( {
    "ajax": "/updateDownloading",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize,     "targets" : 1 },
        { "render": formatProgress, "targets" : 2 },
        { "render": formatBPS,      "targets" : 3 },
        { "render": formatTimeDiff, "targets" : 4 },
        { "render": formatTimeDiff, "targets" : 5 }
    ],
    "columns" : [
        {  className: "aLeft" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" }
    ],
    "order": [[ 2, "desc" ]]
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
        {  className: "aLeftt" },
        {  className: "aRight" },
        {  className: "aCenter" },
        {  className: "aRight" },
        {  className: "aCenter" }
    ],
    "order": [[ 4, "desc" ]]
} );


updater = self.setInterval(updateTabData, {updateRate});

getLog();
 
});
