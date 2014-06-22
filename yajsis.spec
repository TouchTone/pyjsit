# -*- mode: python -*-
import glob

a = Analysis(['yajsis.py'],
             pathex=['Q:\\home\\reiners\\work\\jsit\\pyjsit'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)

a.datas += [ ('defaults.json', 'defaults.json', 'DATA'), ('example.json', 'example.json', 'DATA'), ('intorrents/Put_Torrents_to_upload_here', 'intorrents/Put_Torrents_to_upload_here', 'DATA')]

# From http://stackoverflow.com/questions/11322538/including-a-directory-using-pyinstaller
##### include mydir in distribution #######
def extra_datas(mydir):
    def rec_glob(p, files):
        import os
        import glob
        for d in glob.glob(p):
            if os.path.isfile(d):
                files.append(d)
            rec_glob("%s/*" % d, files)
    files = []
    rec_glob("%s/*" % mydir, files)
    extra_datas = []
    for f in files:
        extra_datas.append((f, f, 'DATA'))

    return extra_datas
###########################################

a.datas += extra_datas("yajsis_resources")

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='yajsis.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='yajsis')
