#!/usr/local/anaconda/bin/python

import numpy as np
import xray
import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt
import my_functions

#=================================================================#
# Parameter setting
#=================================================================#
rvic_output_path = '/raid2/ymao/VIC_RBM_east_RIPS/RIPS/model_run/output/RVIC/Tennessee_8th_grid/hist/Tennessee_UH_1.hist_1949_2010.calibrated_1961_1970.rvic.h0a.2011-01-01.nc'
dam_lat = float(35.9375)
dam_lon = float(-83.4375)
TVA_daily_path = '/raid2/ymao/VIC_RBM_east_RIPS/data/TVA_data/naturalized_flow/downscaled_daily_flow/dams/dam7.daily.1903_2013' # Daily TVA pass-through flow data
output_plot_dir = './output'
USGS_path = '/raid2/ymao/VIC_RBM_east_RIPS/RIPS/model_run/result_analysis/data/USGS_data/Tennessee/03469000.txt'

start_date = dt.datetime(1949,1,1)  # start and end date for simulating reservoir operation
end_date = dt.datetime(2010,12,31)

# Reservoir operation parameters
top_vol = 1461000  # Reservoir top volumn [acre-feet]
bot_vol = 0  # Reservoir bottom volumn [acre-feet]
max_flow = 15000  # Maximum flow [cfs]
min_flow = 585  # Minimum flow [cfs]
init_S = 379000  # Initial storage (typically equal to winter rule curve) [acre-feet]
rule_curve_path = './input/Douglas.txt'  # Annual rule curve data; month, day, rule_curve [arce-feet]; 365 days

#=================================================================#
# Parameter processing
#=================================================================#
print 'Parameter processing...'
# Convert units
top_vol = top_vol * 43560.0  # convert [acre-feet] to [ft3]
bot_vol = bot_vol * 43560.0  # convert [acre-feet] to [ft3]
init_S = init_S * 43560.0  # convert [acre-feet] to [ft3]

# Rule curve processing
rule_curve_annual = np.loadtxt(rule_curve_path, skiprows=1)  # Load annual rule curve data
rule_curve_annual[:,2] = rule_curve_annual[:,2] * 43560.0  # convert [acre-feet] to [ft3]
s_rule_curve = pd.Series(index=pd.date_range(start_date,end_date))  # create empty Series

for i in range(len(rule_curve_annual)):  # loop over each day of year
    month = int(rule_curve_annual[i,0])
    day = int(rule_curve_annual[i,1])
    s_rule_curve.loc[(s_rule_curve.index.month==month) & (s_rule_curve.index.day==day)] = rule_curve_annual[i,2]
s_rule_curve.loc[(s_rule_curve.index.month==2) & (s_rule_curve.index.day==29)] = rule_curve_annual[58,2] # set 2/29 equal to 2/28

#=================================================================#
# Load data
#=================================================================#
# Load simulated streamflow data
print 'Loading simulated flow data...'
data_rvic = xray.open_dataset(rvic_output_path)
data_rvic = data_rvic['streamflow'][:-1,:,:]  # delete last junk date
s_rvic_flow = data_rvic.loc[:,dam_lat,dam_lon].to_series()
s_rvic_flow = s_rvic_flow * pow(1000./25.4/12, 3)  # convert m3/s to cfs

# Load daily TVA flow data
print 'Loading TVA flow data...'
s_tva_flow = my_functions.read_Lohmann_route_daily_output(TVA_daily_path)

# Load USGS observed flow data
print 'Loading USGS flow data...'
s_usgs_flow = my_functions.read_USGS_data(USGS_path, [1], ['usgs_flow']).ix[:,0]

# Select time range
s_rvic_flow = my_functions.select_time_range(s_rvic_flow, start_date, end_date)
s_tva_flow = my_functions.select_time_range(s_tva_flow, start_date, end_date)
s_usgs_flow = my_functions.select_time_range(s_usgs_flow, start_date, end_date)

#=================================================================#
# Reservoir operation simulating
#=================================================================#
print 'Simulating reservoir operation...'
# Initialize
storage = pd.Series(index=pd.date_range(start_date,end_date))  # initialize storage ts [acre-feet]
release = pd.Series(index=pd.date_range(start_date,end_date))  # initialize release ts [cfs]
S = init_S
# Loop over each day
for t in range(len(s_rule_curve)):
    # Maximum available water to release
    max_avail = S + s_rvic_flow[t]*86400 - bot_vol  # [ft3/day]
    # Rease required to bring storage to rule curve
    rule_req = max(0, S + s_rvic_flow[t]*86400 - s_rule_curve[t])  # [ft3/day]
    # Additional flood max capacity
    flood_cap = top_vol - s_rule_curve[t]  # [ft3]
    # Step 1 - preliminary release
    prelim_release = min(max_avail, max(rule_req, min_flow*86400))  # [ft3/day]
    # Step 2 - final release (check flood)
    reduced_release = max(max_flow*86400, prelim_release - flood_cap)  # [ft3/day]
    if prelim_release <= max_flow*86400:
        final_release = prelim_release
    else:
        final_release = reduced_release  # [ft3/day]
    release[t] = final_release / 86400.0  # convert to [cfs]
    # Update storage
    S = S + s_rvic_flow[t]*86400 - final_release
    storage[t] = S

#=================================================================#
# Plotting
#=================================================================#
#============ Select data range to plot ============#
# determine the common range of available data of both data sets
data_avai_start_date, data_avai_end_date = my_functions.\
                        find_data_common_range([s_usgs_flow, s_rvic_flow, s_tva_flow])
if (data_avai_start_date-data_avai_end_date).days>=0: # if no common time range
    print "No common range data available!"
#    exit()

# find the full water years with available data for both data sets
plot_start_date, plot_end_date = my_functions.\
        find_full_water_years_within_a_range(data_avai_start_date, data_avai_end_date)

# Select better time range
s_rvic_flow_to_plot = my_functions.select_time_range(s_rvic_flow, plot_start_date, plot_end_date)
s_tva_flow_to_plot = my_functions.select_time_range(s_tva_flow, plot_start_date, plot_end_date)
s_usgs_flow_to_plot = my_functions.select_time_range(s_usgs_flow, plot_start_date, plot_end_date)
release_to_plot = my_functions.select_time_range(release, plot_start_date, plot_end_date)

# Plot seasonality
fig = my_functions.plot_seasonality_data([s_tva_flow/1000, s_usgs_flow/1000, s_rvic_flow/1000, release/1000], \
                            list_style=['k-', 'b-', 'r--', 'm--'], \
                            list_label=['TVA flow', 'USGS observed flow', 'Simulated unregulated flow', \
                                        'Simulated regulated flow'], \
                            plot_start=1, plot_end=12, \
                            xlabel=None, ylabel='Flow (thousand cfs)', \
                            title='Dam Douglas, WY{}-{}'.format(plot_start_date.year+1, plot_end_date.year), \
                            fontsize=16, legend_loc='upper right', \
                            xtick_location=range(1,13), \
                            xtick_labels=['Jan','Feb','Mar','Apr','May','Jun', \
                                          'Jul','Aug','Nov','Oct','Nov','Dec'], \
                            add_info_text=False, model_info=None, stats=None, show=False)
fig.savefig('{}/Douglas.season.max_flow_{}.png'.format(output_plot_dir, max_flow), \
                                                       format='png')

# plot storage
fig = plt.figure()
plt.plot_date(s_rule_curve.index, s_rule_curve/ 43560.0, 'b-', label='rule curve')
plt.plot(storage.index, storage/ 43560.0, 'm-', label='storage')
plt.legend(loc='upper center')
plt.xlabel('Storage (acre-feet)', fontsize=16)
fig.savefig('./output/Douglas.storage.png', format='png')
plt.show()

