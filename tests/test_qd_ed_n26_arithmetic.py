import pytest
from scripts.qd_ed_n26_reference import layout_name,LAYOUTS

@pytest.mark.parametrize('value',[None,[],[1,2,3],[8192,128,True],[-1,128,1]])
def test_unknown_stride_never_silently_contiguous(value):
    with pytest.raises(ValueError):layout_name(value)

@pytest.mark.parametrize('name',LAYOUTS)
def test_declared_layout_unique(name):
    assert layout_name(list(LAYOUTS[name][0]))==name
