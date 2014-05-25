

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
    
    d = new Date(data * 1000) 

    return d.toLocaleString();
}

function formatSize(data, type, row)
{
    if (type == "sort" || type == "type")
        return +data;
        
    pref = "";
    
    if      (data >= 1000000000) { pref = "G"; num = (data / 1000000000).toFixed(2); }
    else if (data >= 1000000)    { pref = "M"; num = (data / 1000000)   .toFixed(2); }
    else if (data >= 1000)       { pref = "K"; num = (data / 1000)      .toFixed(2); }
    else                        { num = data; }
    
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

function updateTabData()
{
    if (isHidden())
    {
        return
    }
    
    var active = $( "#tabs" ).tabs( "option", "active" );
    
    if      (active == 0) { $.getJSON("/updateLog", function( data ) { $("#div_log").append(data); } ); }
    else if (active == 2) { tabTorrents.ajax.reload(null, false); }
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


function startDownload(hash)
{
    $.get('/startDownload', { "hash": hash })
    
    setTimeout(updateTabData(), 400);
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


var tabTorrents = $('#tab_torrents').DataTable( {
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

var tabChecking = $('#tab_checking').DataTable( {
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
    ]
} );

var tabDownloading = $('#tab_downloading').DataTable( {
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
    ]
} );

var tabFinished = $('#tab_finished').DataTable( {
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
        {  className: "aRight" }
    ]
} );


var updater = self.setInterval(updateTabData, 5000);
getLog();
 
});
