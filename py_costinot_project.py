# Python code for Costinot et al project

import numpy as np
import pandas as pd
import pyhdfe
import statsmodels.formula.api as smf
import statsmodels.api as sm
# from linearmodels.panel import PanelOLS
from fixedeffect.fe import fixedeffect, getfe

wiot = pd.read_csv("output/wiot.csv").drop(columns='Unnamed: 0')

wiod_sea = pd.read_excel("input/WIOD_SEA_Nov16.xlsx",
                         sheet_name="DATA",
                         engine="openpyxl")
employed = (wiod_sea
            .query("variable == 'EMP'")
            .groupby('country')[2014]
            .sum()
            .reset_index()
            .rename(columns={'country': 'out_country', 2014: 'employed_i'})
            )
row = pd.DataFrame({'out_country': ['ROW'],
                    'employed_i': [employed['employed_i'].sum()]})
employed = employed.append(row)
employed.to_csv("output/employed.csv", index=False)

# Starting calibration
theta = 6.534

trade_flows = wiot.copy()  # Just to keep names the same as in R code
# Helps in cleaner code
ijk_cols = ['out_country', 'in_country', 'out_ind']
trade_flows = (trade_flows
               .groupby(ijk_cols, as_index=False)[['value']]
               .sum()
               )
trade_flows['log1_value'] = np.log(trade_flows['value'] + 1)
trade_flows['delta_ij'] = trade_flows['out_country'] + \
    '_' + trade_flows['in_country']
trade_flows['delta_jk'] = trade_flows['in_country'] + \
    '_' + trade_flows['out_ind'].astype(str)
trade_flows['delta_ik'] = trade_flows['out_country'] + \
    '_' + trade_flows['out_ind'].astype(str)

# Run a fixed-effect regression to extract the revealed productivities
# This takes 1 minute and crashes
# eq19 = smf.ols('log1_value ~ C(delta_ij)+C(delta_jk)+C(delta_ik)',
#                data=trade_flows).fit()
# # FixedEffect library
# mod = fixedeffect(data_df=trade_flows,
#                   dependent=['log1_value'],
#                   exog_x=[],
#                   category=['delta_ij', 'delta_jk', 'delta_ik'],
#                   cluster=['delta_ij', 'delta_jk', 'delta_ik']).fit()
# mod.summary()
# fes = getfe(mod, normalize=True) # Error

# # pyhdfe library
# ids = trade_flows[['delta_ij', 'delta_jk', 'delta_ik']]
# variables = trade_flows[['log1_value']]
# algorithm = pyhdfe.create(ids)
# residualized = algorithm.residualize(variables)
# residualized
# reg = sm.OLS(residualized, np.ones(len(residualized))).fit(cov_type='HC1')
# reg.summary() # Dead-end, cannot retrieve FEs

# SOLUTION: make the regression in R and load the fixed-effects back
z_ik = pd.read_csv("output/z_ik.csv")
z_ik['z_ik'] = np.exp(z_ik['fe']/theta)
z_ik['out_country'] = z_ik['delta_ik'].str.split('_').apply(lambda x: x[0])
z_ik['out_ind'] = z_ik['delta_ik'].str.split('_').apply(lambda x: x[1]).astype('int64')
# Merge back into trade_flows as this is our main dataset. Both z_ik and z_jk
trade_flows = trade_flows.merge(z_ik[['out_country', 'out_ind', 'z_ik']],
                                how='left',
                                left_on=['in_country', 'out_ind'],
                                right_on=['out_country', 'out_ind'])
trade_flows.rename(columns={'z_ik': 'z_jk', 'out_country_x': 'out_country'},
                   inplace=True)
trade_flows = trade_flows.merge(z_ik[['out_country', 'out_ind', 'z_ik']],
                                how='left',
                                on=['out_country', 'out_ind'])
trade_flows.drop('out_country_y', axis=1, inplace=True)