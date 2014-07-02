
// Helpers 

// From http://stackoverflow.com/questions/646628/how-to-check-if-a-string-startswith-another-string
if (typeof String.prototype.startsWith != 'function') {
  String.prototype.startsWith = function (str){
    return this.slice(0, str.length) == str;
  };
}
if (typeof String.prototype.endsWith != 'function') {
  String.prototype.endsWith = function (str){
    return this.slice(-str.length) == str;
  };
}

// From http://stackoverflow.com/questions/3431512/javascript-equivalent-to-phps-urldecode
function urldecode (str) {
  return decodeURIComponent((str + '').replace(/\+/g, '%20'));
}

// State Vars

var api_key;
chrome.storage.sync.get('apikey', function (result) { api_key = result.value; });

var add_buttons;
chrome.storage.sync.get('addbuttons', 
function (result) 
{ 
    if (typeof result.value == "undefined")
    {
        add_buttons = true;
    }
    else
    {
        add_buttons = result.value; 
    }
});


// helper to check if a url is a torrent url

function getURLType(url)
{
    var patterns = [    "/download/file.php\\?id=",
                        "/download.php\\?torrent=",
                        "/torrent/download/",
                        "/torrents/[0-9]*/file",
                        "/torrents.php\\?action=download",
                        "/download.php\\?id="
                    ];
                        

    if (url.startsWith("magnet:"))
    {
        return "magnet";
    }
    else if (url.match("/^[0-9a-fA-F]{40}$/"))
    {
        return "hash";
    }    
    else if (url.endsWith(".torrent"))
    {
        return "torrent";
    }
    
    var n = patterns.length;
    for (var i = 0; i < n; i++)
    {
        if (url.search(patterns[i]) != -1)
        {
            return "torrent";
        }
    }
    
    return "No";
}

// Actions

function send_form(url, formData, sendResponse)
{
    console.log("Uploading " + formData + " to JSIT...");
    
    var http = new XMLHttpRequest();    
    http.open("POST", url, true);

    http.onreadystatechange = function() {
        if(http.readyState == 4) 
        {
            resp = http.responseXML;
            s = resp.getElementsByTagName("status")[0].innerHTML;
            
            if ( s != "SUCCESS" )
            {
                m = urldecode(resp.getElementsByTagName("message")[0].innerHTML);
                alert("Torrent upload failed!\n"+ m);
                sendResponse("failure");
            }
            else
            {
                 sendResponse("success");          
            }
        }
    };
  
    http.send(formData);
}

function upload_url(url, sendResponse)
{
    if (typeof api_key == 'undefined')
    {
        alert("Please set your api_key before trying to upload torrents!");
        sendResponse("ignore");
        return;
    }
    
    var url_type = getURLType(url);

    if (url_type == "No")
    {
        alert(url + " is not a recognized torrent link!");
        sendResponse("ignore");
        return;
    }
    
    var apiurl = "https://api.justseed.it/torrent/add.csp";
    
    var formData = new FormData();
    formData.append("api_key", api_key );
    
    if (url_type == "magnet")
    {
        formData.append("url", url );
        
        send_form(apiurl, formData, sendResponse);
    }
    else if (url_type == "hash")
    {
        formData.append("info_hash", url );
        
        send_form(apiurl, formData, sendResponse);
    }
    else if (url_type == "torrent")
    {
        // Download torrent file
        var http = new XMLHttpRequest();
        http.open("GET", url, true);
        http.responseType = 'blob';
        http.onreadystatechange = function() 
        {
            if(http.readyState == 4) 
            {
                if (http.status != 200)
                {
                    alert("Downloading torrent failed: " + http.status + "!");
                }
                else
                {
                    formData.append("torrent_file", http.response );
                    send_form(apiurl, formData, sendResponse);
                }
            };
         };

        http.send();
    }   
}

function dummy(arg)
{
}

function upload(info, tab)
{
    url = info.linkUrl;

    upload_url(url, dummy);
}


// Initialization

chrome.contextMenus.removeAll();
chrome.contextMenus.create({
        "id": "jsit",
        "title": "Upload to JSIT", 
        "contexts": ["link"],
        "onclick": upload
});

// Message listener

chrome.runtime.onMessage.addListener(
  function(request, sender, sendResponse) {
    //console.log(sender.tab ?
    //            "from a content script:" + sender.tab.url :
    //            "from the extension");
    if (request.type == "getApiKey")
    {
        sendResponse({apikey: api_key});
    }
    else if (request.type == "setApiKey")
    {
        api_key = request.value;
        chrome.storage.sync.set({"apikey" : api_key });
    }
    else if (request.type == "getAddButtons")
    {
        sendResponse({addbuttons: add_buttons});
    }
    else if (request.type == "setAddButtons")
    {
        add_buttons = request.value;
        chrome.storage.sync.set({"addbuttons" : add_buttons });
    }
    else if (request.type == "uploadURL")
    {
        url = request.value;
        upload_url(url, sendResponse);
            
        return true;
    }
  });
