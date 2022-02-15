# Python code for Costinot et al project

import numpy as np
import pandas as pd

wiot = pd.read_csv("output/wiot.csv").drop(columns='Unnamed: 0')
# Flooring values lower than one. Cheap trick to avoid division by zero
# further down
wiot.loc[wiot['value'] < 1.0, 'value'] = 1.0


wiod_sea = pd.read_excel("input/WIOD_SEA_Nov16.xlsx",
                         sheet_name="DATA",
                         engine="openpyxl")
employed = (wiod_sea
            .query("variable == 'EMP'")
            .groupby('country', as_index=False)[2014]
            .sum()
            .rename(columns={'country': 'out_country', 2014: 'employed_i'})
            )
row = pd.DataFrame({'out_country': ['ROW'],
                    'employed_i': [employed['employed_i'].sum()]})
employed = employed.append(row)
# employed.to_csv("output/employed.csv", index=False)

# Starting calibration
theta = 6.534

trade_flows = wiot.copy()  # Just to keep names the same as in R code
# Helps in cleaner code
ijk_cols = ['out_country', 'in_country', 'out_ind']
ij_cols = ['out_country', 'in_country']
ik_cols = ['out_country', 'out_ind']
jk_cols = ['in_country', 'out_ind']

trade_flows = (trade_flows
               .groupby(ijk_cols, as_index=False)[['value']]
               .sum()
               )
trade_flows['log1_value'] = np.log(trade_flows['value'] + 1)
# trade_flows['delta_ij'] = trade_flows['out_country'] + \
#     '_' + trade_flows['in_country']
# trade_flows['delta_jk'] = trade_flows['in_country'] + \
#     '_' + trade_flows['out_ind'].astype(str)
# trade_flows['delta_ik'] = trade_flows['out_country'] + \
#     '_' + trade_flows['out_ind'].astype(str)

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
z_ik['out_ind'] = (z_ik['delta_ik'].str.split('_').apply(lambda x: x[1])
                   .astype('int64'))
# Merge back into trade_flows as this is our main dataset. Both z_ik and z_jk
trade_flows = trade_flows.merge(z_ik[['out_country', 'out_ind', 'z_ik']],
                                how='left',
                                left_on=jk_cols,
                                right_on=ik_cols)
trade_flows.rename(columns={'z_ik': 'z_jk', 'out_country_x': 'out_country'},
                   inplace=True)
trade_flows.drop('out_country_y', axis=1, inplace=True)
trade_flows = trade_flows.merge(z_ik[['out_country', 'out_ind', 'z_ik']],
                                how='left',
                                on=ik_cols)
# share of expenditures in k industry for in_country j. This must be computed
# from in_ind!! It's the industry k where the importer country is spending
alpha_jk = (wiot
            .groupby(['in_country', 'in_ind'], as_index=False)['value']
            .sum())
alpha_jk['alpha_jk'] = (alpha_jk
                        .groupby('in_country', as_index=False)['value']
                        .transform(lambda x: x/sum(x)))
alpha_jk.drop('value', axis=1, inplace=True)
# Compatibilize industry name with the rest of data
alpha_jk.rename(columns={'in_ind': 'out_ind'}, inplace=True)
# Check alphas sum to one
alpha_jk.groupby('in_country')['alpha_jk'].sum().describe()

# Estimating pi_ijk
pi_ijk = trade_flows[['in_country', 'out_ind', 'out_country']]
pi_ijk['pi_ijk'] = (trade_flows
                    .groupby(['in_country', 'out_ind'], as_index=False)['value']
                    .transform(lambda x: x/sum(x)))
# Compute pi_jjk since its useful to estimate trade costs
pi_jjk = pi_ijk[pi_ijk['out_country'] == pi_ijk['in_country']]
pi_ijk = pi_ijk.merge(pi_jjk.drop('out_country', axis=1),
                      on=['in_country', 'out_ind'],
                      how='left')
pi_ijk.rename(columns={'pi_ijk_x': 'pi_ijk', 'pi_ijk_y': 'pi_jjk'},
              inplace=True)
# ' Check $\pi_{ij}^k$ sum to one over in_country and out_ind
pi_ijk.groupby(['in_country', 'out_ind'])['pi_ijk'].sum().describe()
# Clean environment
del pi_jjk

# Matching wages to guarantee balanced trade
lambda_ij = pi_ijk.merge(alpha_jk, on=jk_cols, how='left')
lambda_ij['lambda_ij'] = lambda_ij['pi_ijk']*lambda_ij['alpha_jk']
lambda_ij = (lambda_ij
             .groupby(ij_cols, as_index=False)['lambda_ij']
             .sum())
# Creates the Lambda matrix
Lambda_mat = lambda_ij.pivot(index='out_country',
                             columns='in_country',
                             values='lambda_ij')
# Vector of gamma guesses
n_countries = Lambda_mat.shape[0]
gamma_old = pd.Series(np.ones(n_countries) / n_countries,
                      index=Lambda_mat.index)
# Iteration to find eigenvalue
for i in range(1000):
    gamma_new = Lambda_mat @ gamma_old
    if max(abs(gamma_new - gamma_old)) < 1e-5:
        break

    gamma_old = gamma_new.copy()

gamma_i = gamma_new.to_frame(name='gamma_i').reset_index()
# Merge Socio-Economic data
gamma_i = gamma_i.merge(employed, on='out_country', how='left')
# Normalize USA wages to 1 and compute the world's wage bill \sum_i w_i L_i
usa_idx = gamma_i['out_country'] == 'USA'
wld_wage = gamma_i.loc[usa_idx, 'employed_i'] / gamma_i.loc[usa_idx, 'gamma_i']
gamma_i['wage_i'] = (gamma_i['gamma_i'] * wld_wage.values
                     / gamma_i['employed_i'])
# Check gamma_i dataframe
gamma_i
# Merge everything back to trade_flows, the main database
trade_flows = (trade_flows
               .merge(alpha_jk, on=jk_cols, how='left')
               .merge(pi_ijk, on=ijk_cols, how='left')
               .merge(gamma_i, on=['out_country'], how='left')
               .merge(gamma_i, left_on='in_country', right_on='out_country',
                      how='left'))
trade_flows.drop('out_country_y', axis=1, inplace=True)
trade_flows.rename(columns={'out_country_x': 'out_country',
                            'gamma_i_x': 'gamma_i',
                            'employed_i_x': 'employed_i',
                            'wage_i_x': 'wage_i',
                            'gamma_i_y': 'gamma_j',
                            'employed_i_y': 'employed_j',
                            'wage_i_y': 'wage_j'},
                   inplace=True)
# Clean environment
# del alpha_jk, pi_ijk, gamma_i, gamma_old, gamma_new, Lambda_mat, lambda_ij, usa_idx, row, usa_idx, z_ik

# Computing trading costs
trade_flows = (trade_flows
               .assign(delta_ijk=lambda x: x['pi_ijk'] / x['pi_jjk'],
                       z_ratio_ijk=lambda x: x['z_ik'] / x['z_jk'],
                       w_ratio_ij=lambda x: x['wage_i'] / x['wage_j'])
               )
trade_flows = (trade_flows
               .assign(d_ijk=lambda x: x['delta_ijk']**(-1/theta)*x['z_ratio_ijk']/x['w_ratio_ij']))
# Insert predicted trade flows and shares into trade_flows
df = trade_flows[['in_country', 'out_ind', 'wage_i', 'd_ijk', 'z_ik']]
df['Phi_jk'] = (df['wage_i']*df['d_ijk'] / df['z_ik'])**(-theta)
df = df.groupby(['in_country', 'out_ind'], as_index=False)['Phi_jk'].agg(sum)
trade_flows = trade_flows.merge(df, on=['in_country', 'out_ind'], how='left')

# Auxilary functions


def pred_value(df):
    return (((df['wage_i']*df['d_ijk'] / df['z_ik'])**(-theta))/df['Phi_jk'])*df['alpha_jk']*df['wage_j']*df['employed_j']


def pred_pi(df):
    return ((df['wage_i']*df['d_ijk'] / df['z_ik'])**(-theta))/df['Phi_jk']


trade_flows['pred_value'] = pred_value(trade_flows)
trade_flows['pred_pi'] = pred_pi(trade_flows)

# Check pred_pi sums to one
trade_flows.groupby(['in_country', 'out_ind'])['pred_pi'].sum()
# predicted pi equals actual pi
trade_flows[ijk_cols + ['pred_pi', 'pi_ijk']].sample(20)
# Correlations
trade_flows[['pred_pi', 'pi_ijk']].corr()
trade_flows[['pred_value', 'value']].corr()
