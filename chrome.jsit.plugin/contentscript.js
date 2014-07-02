

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
   

function sendURL(e)
{
    l = e.target.parentElement.previousElementSibling;
    url = l.href;
    console.log("Sending URL: " + url);
    logourl = chrome.extension.getURL("logo_16_pending.png");
    e.target.src = logourl;
    
    chrome.runtime.sendMessage({type: "uploadURL", value: url}, function(response) {
    
        if (response == "success")
        {
            logourl = chrome.extension.getURL("logo_16_success.png");
            e.target.src = logourl;
        }
        else if  (response == "failure")
        {
            logourl = chrome.extension.getURL("logo_16_failure.png");
            e.target.src = logourl;
        }
        else
        {
            logourl = chrome.extension.getURL("logo_16.png");
            e.target.src = logourl;
        }
    });
}


var add_buttons = true;

chrome.runtime.sendMessage({type: "getAddButtons"}, function(response) {
        add_buttons = response.addbuttons;

        if (add_buttons)
        {
            var links = document.getElementsByTagName('a');

            for(var i=0; i<links.length; i++) 
            {
                l = links[i];
                url = l.href;

                if (getURLType(url) != "No")
                {
                    var jsl = document.createElement("span");
                    jsl.setAttribute("class", "jsit");
                    logourl = chrome.extension.getURL("logo_16.png");
                    jsl.innerHTML = "<img src='" + logourl + "' title='Upload to JSIT'/>";

                    l.parentNode.insertBefore(jsl, l.nextSibling);

                    jsl.addEventListener("click", sendURL, false);
                }
            }
        }
    })
    
