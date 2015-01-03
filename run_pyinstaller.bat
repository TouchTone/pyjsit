set PATH=%PATH%;C:\Python27;C:\Python27\Scripts;C:\Scratch\upx391w;

python update_prefs.py  --defaults

rmdir /s /q dist build

pyinstaller --noconfirm yajsig.spec
pyinstaller --noconfirm yajsis.spec

python merge_dists.py dist/yajsi_all dist/yajsis dist/yajsig

md dist\yajsi_all\downloads
md dist\yajsi_all\completed

set /p VER=<current_version.txt

cd dist
move yajsi_all yajsig_%VER%

..\7z.exe a -sfx yajsig_%VER%.exe  yajsig_%VER%

cd ..
