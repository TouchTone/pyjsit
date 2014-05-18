# -*- mode: python -*-
import glob

a = Analysis(['yajsis.py'],
             pathex=['Q:\\home\\reiners\\work\\jsit\\pyjsit'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)

a.datas += [ ('defaults.json', 'defaults.json', 'DATA'), ('aria2c.exe', 'aria2c.exe', 'DATA'), ('intorrents/Put_Torrents_to_upload_here', 'intorrents/Put_Torrents_to_upload_here', 'DATA')]

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
