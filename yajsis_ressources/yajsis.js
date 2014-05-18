

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
    var time    = days+' days '+hours+':'+minutes+':'+seconds;
    return time;
}


// Datatables helper functions

function formatTimeDiff(data, type, row)
{
    if (type == "sort")
        return +data;
        
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
    var active = $( "#tabs" ).tabs( "option", "active" );
    
    if      (active == 0) { $.getJSON("/updateLog", function( data ) { $("#div_log").append(data); } ); }
    else if (active == 1) { tabTorrents.ajax.reload(null, false); }
    else if (active == 2) { tabPending.ajax.reload(null, false); }
    else if (active == 3) { tabDownloading.ajax.reload(null, false); }
    else if (active == 4) { tabFinished.ajax.reload(null, false); }
    
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
    $("#div_log").html("");
    $.get("/clearLog");
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
        { "render": formatTimeDiff, "targets" : 4 }
    ],
    "columns" : [
        null,
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" },
        {  className: "aRight" },
        {  className: "aCenter" }
    ]
} );

var tabPending = $('#tab_pending').DataTable( {
    "ajax": "/updatePending",
    "pagingType": "full_numbers",
    "aLengthMenu" : [10,15,20,30,50,100],
    "columnDefs": [
        { "render": formatSize, "targets" : 1 },
        { "render": formatProgress, "targets" : 2 }
    ],
    "columns" : [
        null,
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" },
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
        { "render": formatTimeDiff, "targets" : 4 }
    ],
    "columns" : [
        null,
        {  className: "aRight" },
        {  className: "aRight" },
        {  className: "aCenter" },
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
        null,
        {  className: "aRight" },
        {  className: "aCenter" },
        {  className: "aRight" }
    ]
} );


var updater = self.setInterval(updateTabData, 5000);
getLog();
