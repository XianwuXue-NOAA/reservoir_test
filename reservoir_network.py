#!/usr/local/anaconda/bin/python

import sys
import numpy as np
import xray
import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt
import os
import my_functions
import my_functions_full

# Read in config file
cfg = my_functions.read_config(sys.argv[1])

# Process dates
start_date_to_run = dt.datetime(cfg['PARAM']['start_date_to_run'][0], \
                                cfg['PARAM']['start_date_to_run'][1], \
                                cfg['PARAM']['start_date_to_run'][2], 12, 0)
end_date_to_run = dt.datetime(cfg['PARAM']['end_date_to_run'][0], \
                              cfg['PARAM']['end_date_to_run'][1], \
                              cfg['PARAM']['end_date_to_run'][2], 12, 0)

#====================================================================#
# Load dam information and network information
#====================================================================#
#=== Load dam info ===#
df_dam_info = pd.read_csv(cfg['DAM_INFO']['dam_info_csv'])
#=== Load network info ===@
ds_network = xray.open_dataset(cfg['NETWORK']['route_nc'])
da_flowdir = ds_network['Flow_Direction']
da_flowdis = ds_network['Flow_Distance']
velocity = cfg['NETWORK']['wave_velocity']  # wave velocity

#====================================================================#
# Simulate each dam and modify flow downstream
#====================================================================#
#=== Load original flow data (RVIC grid format) ===#
ds_rvic = xray.open_dataset(cfg['INPUT']['rvic_output_path'])
da_rvic_flow = ds_rvic['streamflow'][:-1,:,:]  # delete last junk date
da_rvic_flow = da_rvic_flow * pow(1000./25.4/12, 3)  # convert m3/s to cfs
da_flow = da_rvic_flow.copy()  # flow field, will be modified

#=== Loop over each dam ===#
# Dam list must be from upstream to downstream order!
for i in range(len(df_dam_info)):
    #=== Extract dam info ===#
    lat = df_dam_info.ix[i]['grid_lat']  # dam grid lat
    lon = df_dam_info.ix[i]['grid_lon']  # dam grid lon
    dam_number = df_dam_info.ix[i]['dam_number']  # dam number
    dam_name = df_dam_info.ix[i]['dam_name']  # dam name
    top_vol = df_dam_info.ix[i]['top_vol_acre_feet']  # reservoir top volumn [acre-feet]
    bot_vol = df_dam_info.ix[i]['bot_vol_acre_feet']  # reservoir bottom volumn [acre-feet]
    max_flow = df_dam_info.ix[i]['max_flow_cfs']  # max flow [cfs]
    min_flow = df_dam_info.ix[i]['min_flow_cfs']  # min flow [cfs]
    print 'Simulating dam {}...'.format(dam_number)
    #=== Load and process rule curve ===#
    rule_curve_filename = os.path.join(cfg['DAM_INFO']['rule_curve_dir'], \
                              'dam{}_{}.txt'.format(dam_number, dam_name.replace(' ', '_')))
    s_rule_curve = my_functions.process_rule_curve(rule_curve_filename, \
                                   start_date_to_run, end_date_to_run) # [acre-feet]
    #=== Extract original flow data from RVIC output ===#
    s_rvic_flow = da_flow.loc[:,lat,lon].to_series()
    #=== Simulate reservoir operation ===#
    init_S = s_rule_curve.ix[0]  # set initial storage to the rule curve value of the first day of simulation
    s_release, s_storage = my_functions\
                .simulate_reservoir_operation(s_rvic_flow, s_rule_curve, \
                                              init_S, top_vol, bot_vol, max_flow, min_flow)
    #=== Modify flow for all downstream grid cells ===#
    da_flow = my_functions.modify_flow_all_downstream_cell(\
                        lat, lon, orig_flow=s_rvic_flow[pd.date_range(start_date_to_run, end_date_to_run)], \
                        release=s_release, da_flow=da_flow, dlatlon=cfg['NETWORK']['dlatlon'], \
                        da_flowdir=da_flowdir, da_flowdis=da_flowdis, velocity=velocity)
    

