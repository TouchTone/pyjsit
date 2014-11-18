# pyjsit

Python API for writing scripts for the justseed.it seedbox-y service, plus a GUI client and a server-based HTML client.

This is a first version of a pythonic API to access justseed.it (called JSIT
from now on). It also provides a GUI for using JSIT more or less like a reguler torrent 
client (see YAJSIG below for details) and a HTML-based server to do automatica and/or remote-controlled downloads and 
management (see YAJSIS below).

## Requirements and Installation

For **Windows** if you only care about YAJSIG and/or YAJSIS you can download a binary version on [github](https://github.com/TouchTone/pyjsit/releases). 

For Linux or if you want to change anything in the code you need the source. The best way to get it is directly from github. Just install git and clone the repository: `git clone https://github.com/TouchTone/pyjsit.git`.

In addition to the source you need a few tools/libraries. As the name implies, it is written in [Python](http://www.python.org), so you
need Python (version 2.7, not 3.x) installed. It also uses the non-standard
[requests](http://docs.python-requests.org/en/latest/) and
[BeautifulSoup4](http://www.crummy.com/software/BeautifulSoup/) modules, and the GUI client uses [pyside](http://qt-project.org/wiki/PySide). Many Linux distros have them included, look for something along the lines of `python-cherrypy`, `python-requests` and `python-pyside` in your package installer.

Alternatively you can install [pip](http://www.pip-installer.org/en/latest/installing.html). Every distro has a `python-pip` package, once you have that installed run

```Python 
pip install BeautifulSoup4 requests pyside
````

and you will have everything you need.

To run the actual programs you should change into the source directory and run them as `python yajsig.py` resp. `python yajsis.py`.


## YAJSIG

The GUI is pretty simple and hopefuly fairly self-explanatory (questions should go [here](http://forum.justseed.it/discussion/1044/yajsig-yet-another-justseed-it-gui-and-yajsis-server-alpha-0-5-0)).
On the first start it will ask for the JSIT username and password to use. These are stored 
in the `preferences.json` file (among other things), if you need to remove or change them.

Adding new torrents can be done in 4 ways:

- `+ Files`: Add selected torrent files
- `+ URL`: Add from an `http://` or `magnet:` URL
- `Watch Clipboard`: Watch the clipboard for `magnet:` or `http://...torrent` links and upload them
- `Watch Directory`: Watch the `intorrents` directory in the program folder for `.torrent` files

Torrents that have been added this way are automatically downloaded into the
`downloads` folder  once they are finished on JSIT (can be changed in the
right click menu). The system checks whether the file(s) already exist and
skips files that are complete and correct. Torrents that are already on
JSIT when the program starts are displayed the same way, but are not marked
for automatic downloading. To download these just check the `Download  when
finished` checkboxes in the appropriate rows or just use the right-click menu.

**Note:** The GUI reflects the status of the JSIT server. Thus some actions
can take a few seconds to show up in the GUI, depending on how long it takes to
transmit them to the server and get the result back. Some actions, especially
adding torrents and starting downloads can actually take quite a while
before the results become visible. Before posting bug reports, please make
sure that things didn't just happen a few seconds late.

Please use http://forum.justseed.it/discussion/1044/yajsig-yet-another-justseed-it-gui-and-yajsis-server-alpha-0-5-0
for feature discussions and discussions and https://github.com/TouchTone/pyjsit/issues for bugs.


## YAJSIS

The goal of YAJSIS is to run it on a server and control it via a web browser from a different machine (which could be in a different place). It does not try to replicate all the justseed.it web functionality, it is really targeted at starting and controlling the download process. It's probably not totally self-explanatory, but it should be pretty straightforward to use with the right expectations: downloading.

It is configured using the same preferences.json file as YAJSIG. I would recommend playing with YAJSIG to find the settings that you want then then copy them over to the YAJSIS directory on the server. You can also run it without a preferences file, but then you need to pass the username and password on the commandline.

Given that it's written in Python it should run pretty much anywhere. By default it runs on port 8282 (changeable with the "--port=" command line option or in the preferences file), so make sure that port is open in the firewall, or use an ssh tunnel to log into the server and tunnel the connection to your local machine for access (look at the -L option for ssh).

Word of warning: even though it looks like a nice, interactive, responsive HTML5 application, be aware that there are two levels of servers in the middle when interacting with it (the yajsis server and the JSIT server), so some actions can take a little while before you see a result (e.g. starting a download). Patience, grasshopper! ;)

## preferences.json

As there is no configuration GUI right now all configurations need to be in the preferences.json file. Make sure you edit it with a Unicode-aware editor
(like Notepad++ or SciTe). Most of it should be relatively obvious (if not, post questions [here](http://forum.justseed.it/discussion/1044/yajsig-yet-another-justseed-it-gui-and-yajsis-server-alpha-0-5-0)). 

The one part that is definitely not obivous is the auto-download. Auto-download has some basic configurations variables that are simple, and a list of 
`types`. Each type has a few variables to configure it's behavior. Example:

```xml
      "CatPictures": {
        "completedDirectory": "E:\\completed\\CatPictures", 
        "deleteSkippedAndStopped": true, 
        "matchLabels": [
          "CatPictures"
        ], 
        "matchNames": [], 
        "priority": 70
      }
```

The variables are:

- `completedDirectory`: Where completed torrents of this type should be moved
- `deleteSkippedAndStopped` : whether to delete torrents of this type that have a `skipLabel` and are stopped (usually because they expired or have exhausted their upload ratio settings)
- `matchLabels` : list of labels that denote a torrent being of this type, actually interpreted as REs
- `matchNames` : ditto
- `priority` : which priority (0-100) to use for this type

Feel free to ask questions in the thread mentioned above.


## Library Concepts

The basics should be pretty obvious after looking at the examples (example_*.py). One thing
that is not going to be obvious is the update rate for the JSIT classes.

To avoid hammering the JSIT servers every time a variable is requested, the
JSIT responses are cached. The time for the cachine depends on the data, basic
info like completed percentage is cached for just 60 seconds, less quickly
changing data like the tracker or peer data is cached for 300, and data that is
unlikely to change at all, like the list of files, forever. There are methods
to explicitly update the data if needed, but please use them carefully. If you overload the servers, your account will be
suspended!

More explanations will come as questions come in, so if something looks
strange or you just cannot figure out, please send me an email or post it in
the JSIT forum at http://forum.justseed.it/discussion/626/jsit-py-python-api.

Enjoy!

## This is so cool, can I buy you a beer?

Unfortunately I don't drink beer. :(

But I like books and gadgets! So if you're serious I'd very much appreciate if you could send me an 
[Amazon Gift Card](https://www.amazon.com/gp/product/B004LLIKVU) to touch_tone@mail.com . Thanks!

Acknowledgement: the icons used are from the Crystal Clear Iconset 
(http://www.iconarchive.com/show/crystal-clear-icons-by-everaldo.html).