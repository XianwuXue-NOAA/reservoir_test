#!/usr/local/anaconda/bin/python

# This script determines maximum flow release at each dam

import csv
import pandas as pd
import os
import matplotlib.pyplot as plt
import datetime as dt
import my_functions

#================================================#
# Parameter setting
#================================================#
dam_to_model_info_path = '/raid2/ymao/VIC_RBM_east_RIPS/reservoir_test/input/reservoir_to_model.csv'
usgs_gauge_info_path = '/raid2/ymao/VIC_RBM_east_RIPS/data/USGS/streamflow/USGS_location_interested_for_dams.csv'
usgs_data_dir = '/raid2/ymao/VIC_RBM_east_RIPS/data/USGS/streamflow' # <usgs_data_dir>/<usgs_code>.txt
TVA_daily_dir = '/raid2/ymao/VIC_RBM_east_RIPS/data/TVA_data/naturalized_flow/downscaled_daily_flow/latlon' # <TVA_daily_dir>/<lat>_<lon>.daily.1903_2013
exceedence = 0.1  # exceedence (based on daily data) for determining max flow

output_dam_info_new_path = './output/reservoir_to_model_new.csv'

#================================================#
# Load dam to model and USGS gauge info
#================================================#
df_dam_info = pd.read_csv(dam_to_model_info_path)
df_usgs_info = pd.read_csv(usgs_gauge_info_path, dtype={'USGS_code':str})

#================================================#
# Process each dam
# If has USGS gauge data, use USGS data to calculate max flow (10% exceedence, daily data)
# If doesn't have USGS data, use TVA data to calculate max flow (10% exceedence, daily data)
# If no USGS or TVA data, don't calculate
#================================================#
#=== Loop over each dam ===#
for i in range(len(df_dam_info)):
    #=== Get dam info ===#
    lat = df_dam_info.ix[i, 'grid_lat']
    lon = df_dam_info.ix[i, 'grid_lon']
    dam_number = df_dam_info.ix[i, 'dam_number']
    dam_name = df_dam_info.ix[i, 'dam_name']
    year_operated = df_dam_info.ix[i, 'year_operated_start_of_Calendar_year']
                    # Reservoir operation starts approximately on Jan 1st this year
    flag = -1  # flag for which data to use
    print 'Processing dam {}...'.format(dam_number)

    #=== If has USGS gauge data ===#
    if len(df_usgs_info[df_usgs_info['corresponding_dam_number']==dam_number]) == 1:
        flag = 'USGS'
        #=== Get site information ===#
        usgs_site = df_usgs_info[df_usgs_info['corresponding_dam_number']==dam_number]
        usgs_code = usgs_site['USGS_code'].values[0]
        usgs_col = usgs_site['flow_col'].values[0]
        #=== Get USGS data ===#
        df_usgs = my_functions.read_USGS_data(\
                        os.path.join(usgs_data_dir, '{}.txt'.format(usgs_code)), \
                        columns=[usgs_col], names=['flow'])  # [cfs]
        s = df_usgs.ix[:,0]  # convert df to Series
        #=== Extract time after reservoir starts operating ===#
        s = s.truncate(before=dt.datetime(year_operated,1,1))
        if len(s)==0:  # if no overlaping time
            flag = -1
    
    #=== If doesn't have USGS data, but has TVA data ===#
    else:
        TVA_path = os.path.join(TVA_daily_dir, '{}_{}.daily.1903_2013'.format(lat, lon))
        if os.path.isfile(TVA_path)==True:  # if has TVA data
            flag = 'TVA'
            s_TVA = my_functions.read_Lohmann_route_daily_output(\
                        os.path.join(TVA_daily_dir, '{}_{}.daily.1903_2013'.format(lat, lon)))
            s = s_TVA  # [cfs]
            #=== Extract time after reservoir starts operating ===#
            s = s.truncate(before=dt.datetime(year_operated,1,1))
            if len(s)==0:  # if no overlaping time
                flag = -1

    #=== If there is USGS or TVA data extracted, determine max allowed flow ===#
    if flag!=-1:
        max_flow = my_functions.determine_max_flow_dam(s, exceedence)

    #=== Save results in df ===#
    if flag!=-1:
        df_dam_info.ix[i,'max_flow_cfs'] = max_flow
    else:
        print 'Warning: dam {} does not have either USGS or TVA data!'.format(dam_number)

#================================================#
# Estimate max flow for dams without data
#================================================#
print 'Estimating max flow for dams without data...'

#=== Dam 16 - proportional to dam 11 based on drainage area ===#
max_flow_dam11 = df_dam_info[df_dam_info['dam_number']==11]['max_flow_cfs'].values[0]
max_flow_dam16 = max_flow_dam11 / 1571.0 * 2627.0  # areal proportional
df_dam_info.loc[df_dam_info['dam_number']==16, 'max_flow_cfs'] = max_flow_dam16

#=== Dam 52 - use USGS gauge 03592000 value ===#
# Get site information
year_operated = df_dam_info[df_dam_info['dam_number']==52]['year_operated_start_of_Calendar_year'].values[0]
usgs_site = df_usgs_info[df_usgs_info['USGS_code']=='03592000']
usgs_code = '03592000'
usgs_col = usgs_site['flow_col'].values[0]
# Get USGS data
df_usgs = my_functions.read_USGS_data(\
                os.path.join(usgs_data_dir, '{}.txt'.format(usgs_code)), \
                columns=[usgs_col], names=['flow'])  # [cfs]
s = df_usgs.ix[:,0]  # convert df to Series
# Extract time after reservoir starts operating
s = s.truncate(before=dt.datetime(year_operated,1,1))
# Calculate max flow
max_flow_dam52 = my_functions.determine_max_flow_dam(s, exceedence)
df_dam_info.loc[df_dam_info['dam_number']==52, 'max_flow_cfs'] = max_flow_dam52

#=== Dam 54 - use corresponding USGS data before reservoir started operating ===#
# Get site information
usgs_site = df_usgs_info[df_usgs_info['corresponding_dam_number']==54]
usgs_code = usgs_site['USGS_code'].values[0]
usgs_col = usgs_site['flow_col'].values[0]
# Get USGS data
df_usgs = my_functions.read_USGS_data(\
                os.path.join(usgs_data_dir, '{}.txt'.format(usgs_code)), \
                columns=[usgs_col], names=['flow'])  # [cfs]
s = df_usgs.ix[:,0]  # convert df to Series
# Calculate max flow
max_flow_dam54 = my_functions.determine_max_flow_dam(s, exceedence)
df_dam_info.loc[df_dam_info['dam_number']==54, 'max_flow_cfs'] = max_flow_dam54

#================================================#
# Save new dam info to file
#================================================#
df_dam_info.to_csv(output_dam_info_new_path, index=False)




