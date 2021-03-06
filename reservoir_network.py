#!/usr/local/anaconda/bin/python

import sys
import numpy as np
import xray
import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt
import os
import my_functions

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
ds_rvic = ds_rvic.isel(time=slice(0,-1))   # delete last junk date
da_rvic_flow = ds_rvic['streamflow'] * pow(1000./25.4/12, 3)  # convert m3/s to cfs
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
    year_operated = df_dam_info.ix[i]['year_operated_start_of_Calendar_year']
                    # year operation started
    print 'Simulating dam {}...'.format(dam_number)
    #=== Load and process rule curve ===#
    rule_curve_filename = os.path.join(cfg['DAM_INFO']['rule_curve_dir'], \
                              'dam{}_{}.txt'.format(dam_number, dam_name.replace(' ', '_')))
    s_rule_curve = my_functions.process_rule_curve(rule_curve_filename, \
                                    start_date_to_run, end_date_to_run) # [acre-feet]
    # If year start operation is after the period considered, truncate the time before operation
    s_rule_curve = s_rule_curve.truncate(before=dt.datetime(year_operated, 1, 1))
    if len(s_rule_curve)==0:  # if no period is operating, do not simulate
        continue
        
    #=== Extract original flow data from RVIC output ===#
    s_rvic_flow = da_flow.loc[:,lat,lon].to_series()
    #=== Simulate reservoir operation ===#
    init_S = s_rule_curve.ix[0]  # set initial storage to the rule curve value of the first day of simulation
    s_release, s_storage = my_functions\
                .simulate_reservoir_operation(s_rvic_flow, s_rule_curve, \
                                              init_S, top_vol, bot_vol, max_flow, min_flow)
    #=== Modify flow for all downstream grid cells ===#
    da_flow = my_functions.modify_flow_all_downstream_cell(\
                        lat, lon, \
                        orig_flow=s_rvic_flow, \
                        release=s_release, da_flow=da_flow, dlatlon=cfg['NETWORK']['dlatlon'], \
                        da_flowdir=da_flowdir, da_flowdis=da_flowdis, velocity=velocity)    
    #=== Save storage ===#
    df = pd.DataFrame()
    df['year'] = s_storage.index.year
    df['month'] = s_storage.index.month
    df['day'] = s_storage.index.day
    df['storage_acre_ft'] = s_storage.values
    df[['year', 'month', 'day', 'storage_acre_ft']].\
            to_csv('{}.storage.dam{}.txt'.format(cfg['OUTPUT']['out_flow_basepath'], \
                                                 dam_number), \
            sep='\t', index=False)
    
#====================================================================#
# Save modified streamflow to netCDF file
#====================================================================#

#=== Save modified streamflow ===#
ds_flow_new = xray.Dataset({'streamflow': (['time', 'lat', 'lon'], da_flow.values)}, \
                           coords={'lat': (['lat'], ds_rvic['lat'].values), \
                                   'lon': (['lon'], ds_rvic['lon'].values), \
                                   'time': (['time'], da_flow['time'].values)})
ds_flow_new['streamflow'].attrs['units'] = 'cfs'
ds_flow_new['streamflow'].attrs['long_name'] = 'Simulated regulated streamflow'

ds_flow_new.to_netcdf('{}.modified_flow.nc'.format(cfg['OUTPUT']['out_flow_basepath']), \
                      format='NETCDF4_CLASSIC')
ds_flow_new.close()

#=== Save flow change before and after reservoir operation ===#
ds_flow_delta = xray.Dataset({'flow_delta': (['time', 'lat', 'lon'], \
                                             da_flow.values-da_rvic_flow.values)}, \
                             coords={'lat': (['lat'], ds_rvic['lat'].values), \
                                     'lon': (['lon'], ds_rvic['lon'].values), \
                                     'time': (['time'], da_flow['time'].values)})
ds_flow_delta['flow_delta'].attrs['units'] = 'cfs'
ds_flow_delta['flow_delta'].attrs['long_name'] = 'Simulated streamflow difference (regulated-unregulated'

ds_flow_delta.to_netcdf('{}.modified_delta_flow.nc'.format(cfg['OUTPUT']['out_flow_basepath']), \
                        format='NETCDF4_CLASSIC')
ds_flow_delta.close()


