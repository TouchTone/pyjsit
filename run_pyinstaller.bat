set PATH=%PATH%;C:\Python27;C:\Python27\Scripts;C:\Scratch\upx391w;

python update_prefs.py  --defaults

pyinstaller --noconfirm yajsig.spec
pyinstaller --noconfirm yajsis.spec

