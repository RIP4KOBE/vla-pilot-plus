import sys
from pathlib import Path
from scripts import qd_ed_n36_source as source
root=Path(__file__).parent
sys.argv=[str(root/'main.py'),'argument']
before=sys.modules['__main__']
source.run_main(root/'main.py')
assert sys.modules['__main__'] is before
assert ('main',str(root/'main.py')) in source.active().compiled
