#!/usr/local/anaconda/bin/python

import csv
import pandas as pd
import os
import matplotlib.pyplot as plt
import my_functions

#================================================#
# Parameter setting
#================================================#
usgs_gauge_info_path = '/raid2/ymao/VIC_RBM_east_RIPS/data/USGS/streamflow/USGS_location_interested_for_dams.csv'
usgs_data_dir = '/raid2/ymao/VIC_RBM_east_RIPS/data/USGS/streamflow' # <usgs_data_dir>/<usgs_code>.txt
TVA_daily_dir = '/raid2/ymao/VIC_RBM_east_RIPS/data/TVA_data/naturalized_flow/downscaled_daily_flow/latlon' # <TVA_daily_dir>/<lat>_<lon>.daily.1903_2013

out_plot_dir = './output/'

#================================================#
# Load gauge info
#================================================#
df_usgs_info = pd.read_csv(usgs_gauge_info_path, dtype={'USGS_code':str})

#================================================#
# Plot each gauge at dam location
#================================================#
# Loop over each gauge
for i in range(len(df_usgs_info)):
    if df_usgs_info.ix[i,'corresponding_dam_number'] != -1: # for gauges that have corresponding dam
        #=== Get site information ===#
        lat = df_usgs_info.ix[i,'grid_lat_corr']
        lon = df_usgs_info.ix[i,'grid_lon_corr']
        usgs_code = df_usgs_info.ix[i,'USGS_code']
        usgs_col = df_usgs_info.ix[i,'flow_col']
        dam_number = df_usgs_info.ix[i,'corresponding_dam_number']
        dam_name = df_usgs_info.ix[i,'corresponding_dam_name']
        print 'Plotting dam {}...'.format(dam_number)
        
        #=== Get USGS data ===#
        df_usgs = my_functions.read_USGS_data(\
                        os.path.join(usgs_data_dir, '{}.txt'.format(usgs_code)), \
                        columns=[usgs_col], names=['flow']) / 1000 # convert to thousand cfs
        s_usgs = df_usgs.ix[:,0]  # convert df to Series

        #=== Get TVA data ===#
        TVA_path = os.path.join(TVA_daily_dir, '{}_{}.daily.1903_2013'.format(lat, lon))
        if os.path.isfile(TVA_path)==False:  # if corresponding dam has no data
            continue
        s_TVA = my_functions.read_Lohmann_route_daily_output(\
                    os.path.join(TVA_daily_dir, '{}_{}.daily.1903_2013'.format(lat, lon)))
        s_TVA = s_TVA / 1000.0  # convert to thousand cfs

        #=== Extract data within common range ===#
        # determine the common range of available data of both data sets
        data_avai_start_date, data_avai_end_date = my_functions.\
                        find_data_common_range([s_usgs, s_TVA])
        if (data_avai_start_date-data_avai_end_date).days>=0: # if no common time range
            print "No common range data available!"
            exit()
        # find the full water years with available data for both data sets
        plot_start_date, plot_end_date = my_functions.\
                find_full_water_years_within_a_range(data_avai_start_date, data_avai_end_date)
        # determine time locator #
        if plot_end_date.year-plot_start_date.year < 5:  # if less than 5 years
            time_locator = ('year', 1)  # time locator on the plot; 'year' for year; 'month' for month. e.g., ('month', 3) for plot one tick every 3 months
        else:  # if at least 5 years
            time_locator = ('year', (plot_end_date.year-plot_start_date.year)/5)  # time locator on the plot; 'year' for year; 'month' for month. e.g., ('month', 3) for plot one tick every 3 months
        # Select data to be plotted
        s_usgs_to_plot = my_functions.select_time_range(s_usgs, \
                                                        plot_start_date, plot_end_date)
        s_TVA_to_plot = my_functions.select_time_range(s_TVA, \
                                                        plot_start_date, plot_end_date)

        #-------------------------------------------
        df_to_plot = pd.DataFrame(s_TVA_to_plot.values, index=s_TVA_to_plot.index, columns=['tva'])
        df_to_plot['usgs'] = s_usgs_to_plot
        df_to_plot = df_to_plot.dropna()
        s_usgs_to_plot = df_to_plot['usgs']
        s_TVA_to_plot = df_to_plot['tva']
        #-------------------------------------------

        #=== Plot flow duration curves (daily data) ===#
        fig = my_functions.plot_duration_curve(\
            list_s_data=[s_TVA_to_plot, s_usgs_to_plot], \
            list_style=['k-', 'b-'], \
            list_label=['TVA pass-through daily', 'USGS daily'], \
            figsize=(10,10), xlog=False, ylog=True, \
            xlim=None, ylim=None, \
            xlabel='Exceedence', ylabel='Flow (thousand cfs)', \
            title='Dam {}, daily flow duration, WY {}-{}'.format(dam_number, \
                                        plot_start_date.year+1, \
                                        plot_end_date.year), \
            fontsize=18, legend_loc='upper right', \
            add_info_text=True, model_info='Compare USGS flow data with TVA pass-through', \
            stats='Flow duration curve based on daily data', show=False)

        ax = plt.gca()
        for tick in ax.xaxis.get_major_ticks():
            tick.label.set_fontsize(16)
        for tick in ax.yaxis.get_major_ticks():
            tick.label.set_fontsize(16)

        plt.savefig(os.path.join(out_plot_dir, \
                                'dam{}.flow_duration_daily.png'.format(dam_number)), \
                    format='png')




