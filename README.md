# pyjsit

Python API for writing scripts for the justseed.it seedbox-y service.

This is a first version of a pythonic API to access justseed.it (called JSIT
from now on). Take a look at
[example_jsit.py](https://github.com/TouchTone/pyjsit/blob/master/example_jsit.py)
to get an idea of what it can do and how to use it.

The core purpose is to make it easy to write scripts that access/use JSIT, to
simplify the different workflows that people are trying to accomplish, in the
future it could also be used to write a graphical client app. See the smaller
examples to get some ideas, new ideas welcome.

This is a very rough first version, and there will be bugs. If you find one
please open an issue at https://github.com/TouchTone/pyjsit/issues and I will
try to take care of it as soon as I can.

## Requirements

As the name implies, it is written in [Python](http://www.python.org), so you
need Python (version 2.7, not 3.x) installed. It also uses the non-standard
[requests](http://docs.python-requests.org/en/latest/) and
[BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/) modules. You
can get both of these using
[pip](http://www.pip-installer.org/en/latest/installing.html):

```Python pip install BeautifulSoup4 requests ````

If you want to use the downloading features, you also need
[aria2](http://aria2.sourceforge.net/) somewhere in your search path. The
clipboard watcher example uses
[PyQT](http://www.riverbankcomputing.com/software/pyqt/intro).

All of these usually have packages for most Linux distributions, for Mac and
Windows you will need to install them yourselves (feedback on how to best do
that welcome!).

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
the JSIT forum at http://forum.justseed.it/discussion/626/jsit-py-python-api.

Enjoy!



