

function setApiKey()
{
    var keyinp = document.getElementById("apikey_input");
    
    chrome.runtime.sendMessage({type: "setApiKey", value : keyinp.value}); 
}

function setAddButtons()
{
    var addcheck = document.getElementById("add_buttons");    
    
    chrome.runtime.sendMessage({type: "setAddButtons", value : addcheck.checked}); 
}

// Startup helpers

document.addEventListener('DOMContentLoaded', function () {
    var keyinp = document.getElementById("apikey_input");
    
    chrome.runtime.sendMessage({type: "getApiKey"}, function(response) {
        if (typeof response.apikey != "undefined")
        {
            keyinp.value = response.apikey;
        }
        else
        {
            keyinp.value = "";
        }
    });
    
    var keybut = document.getElementById("apikey_submit");
    keybut.addEventListener('click', setApiKey);


    var addcheck = document.getElementById("add_buttons");    
    chrome.runtime.sendMessage({type: "getAddButtons"}, function(response) {
        addcheck.checked = response.addbuttons;
    });
    addcheck.addEventListener('change', setAddButtons);

});

