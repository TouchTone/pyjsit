# -*- mode: python -*-
import glob

a = Analysis(['yajsig.py'],
             pathex=['Q:\\home\\reiners\\work\\jsit\\pyjsit'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)

a.datas += [ ('defaults.json', 'defaults.json', 'DATA'), ('example.json', 'example.json', 'DATA'), ('intorrents/Put_Torrents_to_upload_here', 'intorrents/Put_Torrents_to_upload_here', 'DATA')]

for i in glob.glob("icons/*"):
    a.datas += [(i, i, 'DATA')]

pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='yajsig.exe',
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
               name='yajsig')
