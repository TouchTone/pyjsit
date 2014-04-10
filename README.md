# pyjsit

Python API for writing scripts for the justseed.it seedbox-y service.

This is a first version of a pythonic API to access justseed.it (called JSIT
from now on). It also provides a (rough) GUI for using JSIT more or less like a reguler torrent 
client, see YAJSIG below for details.

## Features

- Easy to use, pythonic library to access JSIT (see `examples_*.py`)
- Wrapper for [aria2](http://aria2.sourceforge.net/) to download data from JSIT
- Managed wrapper that makes the JSIT/aria combination feel like a normal torrent system

### YAJSIG Features

- Full-features GUI for observing torrent activity on JSIT
- Add one or more torrents to JSIT from selected files, files placed in specific directory or from http/magnet links on the clipboard
- Use maximum different ratio for public/private torrents automatically
- Start/stop torrents
- Controls aria to download contents automatically
- Adjust labels and maximum ratio
 

Take a look at
[example_jsit.py](https://github.com/TouchTone/pyjsit/blob/master/example_jsit.py)
to get an idea of what it can do and how to use the API.

The core purpose is to make it easy to write scripts that access/use JSIT, to
simplify the different workflows that people are trying to accomplish. See the smaller
examples to get some ideas, new ideas welcome.

This is a pretty rough alpha version, and there will be bugs. If you find one
please open an issue at https://github.com/TouchTone/pyjsit/issues and I will
try to take care of it as soon as I can.

## Requirements

As the name implies, it is written in [Python](http://www.python.org), so you
need Python (version 2.7, not 3.x) installed. It also uses the non-standard
[requests](http://docs.python-requests.org/en/latest/) and
[BeautifulSoup4](http://www.crummy.com/software/BeautifulSoup/) modules. You
can get both of these using
[pip](http://www.pip-installer.org/en/latest/installing.html):

```Python 
pip install BeautifulSoup4 requests 
````

If you want to use the downloading features, you also need
[aria2](http://aria2.sourceforge.net/) somewhere in your search path. 

The 
clipboard watcher example uses
[PySide](http://qt-project.org), version 4.x.

All of these usually have packages for most Linux distributions, for Mac and
Windows you will need to install them yourselves (feedback on how to best do
that welcome!).

### YAJSIG

The GUI client YAJSIG (Yet Another JSIt Gui, pronounced jaysig) has the same dependencies described above, 
and it does need [PySide](http://qt-project.org to drive the GUI.

If you are on **Windows** you can download a binary version from XXX. (Coming soon) 
Just unpack into a new folder and start the yajsig.exe program. 

The GUI is pretty simple and hopefuly fairly self-explanatory (questions should go [here]()).
On the first start it will ask for the JSIT username and password to use. These are stored 
in the preferences.json file (among other things), if you need to remove or change them.

Adding new torrents can be done in 4 ways:

- `+ Files`: Add selected torrent files
- `+ URL`: Add from an `http://` or `magnet:` URL
- `Watch Clipboard`: Watch the clipboard for `magnet:` or `http://...torrent` links and upload them
- `Watch Directory`: Watch the `intorrents` directory in the program folder for `.torrent` files

Torrents that have been added this way are automatically downloaded into the
`downloads` folder  once they are finished on JSIT (can be changed in the
right click menu). The system checks whether the file(s) already exist and
skips files  that are complete and correct. Torrents that are already on
JSIT when the program starts are displayed the same way, but are not marked
for automatic downloading. To download these just check the `Download  when
finished` checkboxes in the appropriate rows.

**Note:** The GUI reflects the status of the JSIT server. Thus some actions
can take a few seconds to show up in the GUI, depending on how long it takes to
transmit them to the server and get the result back. Some actions, especially
adding torrents and starting downloads can actually take quite a while
before the results become visible. Before posting bug reports, please make
sure that things didn't just happen a few seconds late.

Please use http://forum.justseed.it/discussion/738/introducing-yajsig-yet-another-jsit-gui-alpha-0-2 
for feature discussions and discussions and https://github.com/TouchTone/pyjsit/issues for bugs.


## Concepts

The system has three main components, jsit.py, aria.py and jsit_manager.py.
Jsit.py and aria.py provide low-level wrappers that present jsit and aria as
Python-style data structures. Behind the scenes they use the JSIT HTTP API
resp. the aria XMLRPC interface to control the respective programs. 

Both provide a core manager object (JSIT resp. Aria) that manages the
connectino to the service, you only need one of those for each program. They
both manage a list of individual torrents/downloads that are going on, and the
base objects behave like lists of those lower levels objects with some
additional methods to create new ones.

The basics should be pretty obvious after looking at the examples. One thing
that is not going to be obvious is the update rate for the JSIT classes.

To avoid hammering the JSIT servers every time a variable is requested, the
JSIT responses are cached. The time for the cachine depends on the data, basic
info like completed percentage is cached for just 5 seconds, less quickly
changing data like the tracker or peer data is cached for 60, and data that is
unlikely to change at all, like the list of files, for 3600. There are methods
to explicitly update the data if needed, but please use them carefully.

More explanations will come as questions come in, so if something looks
strange or you just cannot figure out, please send me an email or post it in
the JSIT forum at http://forum.justseed.it/discussion/626/jsit-py-python-api or .

Enjoy!

## This is so cool, can I buy you a beer?

Unfortunately I don't drink beer. :(

But I like books and gadgets! So if you're serious I'd very much appreciate if you could send me an 
[Amazon Gift Card](https://www.amazon.com/gp/product/B004LLIKVU) to touch_tone@mail.com . Thanks!

