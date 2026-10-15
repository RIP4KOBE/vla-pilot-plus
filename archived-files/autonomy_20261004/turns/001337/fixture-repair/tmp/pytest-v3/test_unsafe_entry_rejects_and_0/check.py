import sys,zipimport
from pathlib import Path
root=Path(__file__).parent
zipimport.zipimporter(str(root/'cache.zip')).load_module('only')
