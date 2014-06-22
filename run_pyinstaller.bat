set PATH=%PATH%;C:\Python27;C:\Python27\Scripts;C:\Scratch\upx391w;

python update_prefs.py  --defaults

rmdir /s /q dist

pyinstaller --noconfirm yajsig.spec
pyinstaller --noconfirm yajsis.spec

python merge_dists.py dist/yajsi_all dist/yajsis dist/yajsig

md dist\yajsi_all\downloads
md dist\yajsi_all\completed


