# Test for Costinot et al project
import pytest
import pandas as pd
import numpy as np

# Helps in cleaner code
ijk_cols = ['out_country', 'in_country', 'out_ind']
ij_cols = ['out_country', 'in_country']
ik_cols = ['out_country', 'out_ind']
jk_cols = ['in_country', 'out_ind']

@pytest.fixture
def trade_flows():
    return pd.read_csv("fix_costinot.csv")

def test_log1(trade_flows):
    trade_flows['log1_value'] = np.log(trade_flows['value'] + 1)
    s = pd.Series([10, 5, 0, 0.5, 20, 0, 10, 0.8])
    ls = np.log(s + 1)
    assert trade_flows['log1_value'].equals(ls)