import folium
import folium.plugins as plugins
import streamlit as st
# from streamlit_folium import folium_static, st_folium
import xarray as xr
from syn_sar import *
import numpy.ma as ma
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from PIL import Image
from geemap.foliumap import Map as geeMap
from geemap import random_string
# from osgeo import gdal
import rioxarray as rio

folium.Map.to_html = geeMap.to_html
folium.Map.to_streamlit = geeMap.to_streamlit
folium.Map.add_layer_control = geeMap.add_layer_control

# Reset Output folder
dir = 'output'
if os.path.isdir(dir):
    for f in os.listdir(dir):
        os.remove(os.path.join(dir, f))
else:
    os.mkdir(dir)


def sheet_out(url):
    return url.replace("/edit#gid=", "/export?format=csv&gid=")

# Page Configuration
st.set_page_config(layout="wide")

if 'AOI_str' not in st.session_state:
    st.session_state.AOI_str = 'LowerMekong'

@st.cache()
def get_wl(mode):
    if mode == "Hindcast":
        sheet_link = pd.read_csv('AOI/%s/wl_sheet_hindcast.txt'%(str(curr_region)), sep = '\t')
        hindcast_wl = {}
        for i in range(sheet_link.shape[0]):
            station = pd.read_csv(sheet_out(sheet_link.iloc[i,1]), index_col=0).reset_index(drop = True)
            station.iloc[:,0] = pd.to_datetime(station.iloc[:,0])
            hindcast_wl[sheet_link.iloc[i,0]] = station
        return hindcast_wl
    if mode == "Forecast":
        sheet_link = pd.read_csv('AOI/%s/wl_sheet.txt'%(str(curr_region)), sep = '\t')
        forecast_wl = {}
        for i in range(sheet_link.shape[0]):
            station = pd.read_csv(sheet_out(sheet_link.iloc[i,1]))
            station.iloc[:,0] = pd.to_datetime(station.iloc[:,0])
            forecast_wl[sheet_link.iloc[i,0]] = station
        return forecast_wl

basemaps = {
    'Google Terrain': folium.TileLayer(
        tiles = 'https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
        attr = 'Google',
        name = 'Google Terrain',
    ),
    'Google Satellite Hybrid': folium.TileLayer(
        tiles = 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr = 'Google',
        name = 'Google Satellite Hybrid',
    ),
    'Esri Ocean': folium.TileLayer(
        tiles="https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Ocean",
    ),
}

flood_color = {0: (0.75, 0.75, 0.75, 0.05),
 1: (0, 0, 0.543, 0.7),
 }

# Title and Description
st.title("Forecasting Inundation Extents using REOF Analysis (FIER)-Mekong")
curr_region = st.session_state.AOI_str

row1_col1, row1_col2 = st.columns([2.5, 1])
# Set up Geemap
with row1_col1:
    curr_region = st.session_state.AOI_str
    location = [12.23, 104.79] # NEED FIX!!!!!!!!!!!
    m = folium.Map(
        zoom_start = 7,
        location = location,
        control_scale=True,
        tiles = None
    )

    basemaps['Google Terrain'].add_to(m)
    basemaps['Google Satellite Hybrid'].add_to(m)
    basemaps['Esri Ocean'].add_to(m)
    plugins.Fullscreen(position='topright').add_to(m)
    m.add_child(folium.LatLngPopup())
    folium.LayerControl().add_to(m)

with row1_col2:
    if st.session_state.AOI_str != None:
        st.subheader('Select Date')
        st.markdown('**AOI: %s**'%(curr_region))
        run_type = st.radio('Run type:', ('Hindcast', 'Forecast'))
        curr_region = st.session_state.AOI_str


        if run_type == 'Hindcast':
            with st.form("Run Hindcasted FIER"):
                sheet_link = pd.read_csv('AOI/%s/wl_sheet_hindcast.txt'%(str(curr_region)), sep = '\t')
                hindcast_wl = get_wl("Hindcast")

                test = hindcast_wl[sheet_link.iloc[1,0]]
                min_date = test.iloc[0,0]
                max_date = test.iloc[-1,0]
                date = st.date_input(
                     "Select Hindcasted Date (2008-01-01 to %s):"%(str(max_date)[:10]),
                     value = datetime.date(2018, 10, 17),
                     min_value = min_date,
                     max_value = max_date,
                     )
                submitted = st.form_submit_button("Submit")
                if submitted:
                    hydrosite = pd.read_csv('AOI/%s/hydrosite.csv'%(str(curr_region)))
                    water_level = {}
                    for i in range(hydrosite.shape[0]):
                        site = hydrosite.loc[i,'ID']
                        df = hindcast_wl[site]
                        d = pd.Timestamp(date)
                        water_level[site] = round(df[df['time'] == d].water_level.values[0], 3)

                    location = [12.23, 104.79] # NEED FIX!!!!!!!!!!!
                    m = folium.Map(
                        zoom_start = 7,
                        location = location,
                        control_scale=True,
                        tiles = None,
                    )

                    image_folder = image_output(curr_region, water_level)
                    with xr.open_dataset(image_folder +'/output.nc',) as output:
                        bounds = [[output.lat.values.min(), output.lon.values.min()], [output.lat.values.max(), output.lon.values.max()]]
                        sar_image, z_score_image, water_map_image = output['Synthesized SAR Image'].values, output['Z-score Image'].values, output['Inundation Map'].values

                    water_cmap =  matplotlib.colors.ListedColormap(["silver","darkblue"])
                    water_map_image[np.isnan(water_map_image)] = 0
                    # water_map_image = colorize(water_map_image, water_cmap)

                    # Add Inundation
                    folium.raster_layers.ImageOverlay(
                        image = water_map_image,
                        bounds = bounds,
                        name = 'Inundation Map_' + curr_region ,
                        colormap = lambda x: flood_color[x],
                        show = True
                    ).add_to(m)

                    plugins.Fullscreen(position='topright').add_to(m)
                    basemaps['Google Terrain'].add_to(m)
                    basemaps['Esri Ocean'].add_to(m)
                    basemaps['Google Satellite Hybrid'].add_to(m)
                    m.add_child(folium.LatLngPopup())
                    folium.LayerControl().add_to(m)
                    st.write('Region:\n', curr_region)
                    st.write('Date: \n', date)
            try:
                with open("output/output.tiff", 'rb') as f:
                    st.download_button('Download Latest Innudation Extent Output (.tiff)',
                    f,
                    file_name = "%s_%s.tiff"%(curr_region, date),
                    mime= "image/geotiff")
            except:
                pass

        else:
            with st.form("Run Forecast FIER"):
                sheet_link = pd.read_csv('AOI/%s/wl_sheet.txt'%(str(curr_region)), sep = '\t')
                forecast_wl = get_wl("Forecast")

                test = forecast_wl[sheet_link.iloc[0,0]]
                min_date = test.iloc[0,0]
                max_date = test.iloc[-1,0]

                date = st.date_input(
                     "Select Forecasted Date (%s to %s):"%(min_date.strftime("%Y/%m/%d"), max_date.strftime("%Y/%m/%d")),
                     value = min_date,
                     min_value = min_date,
                     max_value = max_date,
                     )

                submitted = st.form_submit_button("Submit")
                if submitted:
                    hydrosite = pd.read_csv('AOI/%s/hydrosite.csv'%(str(curr_region)))
                    water_level = {}
                    for i in range(hydrosite.shape[0]):
                        site = hydrosite.loc[i,'ID']
                        df = forecast_wl[site]
                        d = pd.Timestamp(date)
                        water_level[site] = round(df[df['time'] == d].water_level.values[0], 3)

                    location = [12.23, 104.79] # NEED FIX!!!!!!!!!!!
                    m = folium.Map(
                        zoom_start = 7,
                        location = location,
                        control_scale=True,
                        tiles = None,
                    )

                    image_folder = image_output(curr_region, water_level)
                    with xr.open_dataset(image_folder +'/output.nc',) as output:
                        bounds = [[output.lat.values.min(), output.lon.values.min()], [output.lat.values.max(), output.lon.values.max()]]
                        sar_image, z_score_image, water_map_image = output['Synthesized SAR Image'].values, output['Z-score Image'].values, output['Inundation Map'].values

                    water_cmap =  matplotlib.colors.ListedColormap(["silver","darkblue"])
                    water_map_image[np.isnan(water_map_image)] = 0
                    # water_map_image = colorize(water_map_image, water_cmap)

                    # Add Inundation
                    folium.raster_layers.ImageOverlay(
                        image = water_map_image,
                        bounds = bounds,
                        name = 'Inundation Map_' + curr_region ,
                        colormap = lambda x: flood_color[x],
                        show = True
                    ).add_to(m)

                    plugins.Fullscreen(position='topright').add_to(m)
                    basemaps['Google Terrain'].add_to(m)
                    basemaps['Esri Ocean'].add_to(m)
                    basemaps['Google Satellite Hybrid'].add_to(m)
                    m.add_child(folium.LatLngPopup())
                    folium.LayerControl().add_to(m)
                    st.write('Region:\n', curr_region)
                    st.write('Date: \n', date)
            try:
                with open("output/output.tiff", 'rb') as f:
                    st.download_button('Download Latest Innudation Extent Output (.tiff)',
                    f,
                    file_name = "%s_%s.tiff"%(curr_region, date),
                    mime= "image/geotiff")
            except:
                pass

    first = Image.open("logo/first.PNG")
    second = Image.open("logo/second_row.PNG")
    st.image([first], width=450,)
    st.image([second], width=350,)


with row1_col1:
    m.to_streamlit(height = 700, scrolling = True)
    st.write('Disclaimer: This is a test version of FIER method for Mekong Region')
    url = "https://www.sciencedirect.com/science/article/pii/S0034425720301024?casa_token=kOYlVMMWkBUAAAAA:fiFM4l6BUzJ8xTCksYUe7X4CcojddbO8ybzOSMe36f2cFWEXDa_aFHaGeEFlN8SuPGnDy7Ir8w"
    st.write("Reference: [Chang, C. H., Lee, H., Kim, D., Hwang, E., Hossain, F., Chishtie, F., ... & Basnayake, S. (2020). Hindcast and forecast of daily inundation extents using satellite SAR and altimetry data with rotated empirical orthogonal function analysis: Case study in Tonle Sap Lake Floodplain. Remote Sensing of Environment, 241, 111732.](%s)" % url)
    url_2 = "https://www.sciencedirect.com/science/article/abs/pii/S1364815218306194"
    st.write("[Chang, C. H., Lee, H., Hossain, F., Basnayake, S., Jayasinghe, S., Chishtie, F., ... & Du Bui, D. (2019). A model-aided satellite-altimetry-based flood forecasting system for the Mekong River. Environmental modelling & software, 112, 112-127.](%s)" % url_2)
    url_3 = "https://ieeexplore.ieee.org/abstract/document/9242297?casa_token=N4ao38AI93gAAAAA:XpEdirsJfsPByzd3no7JLEcrYxXcBVKd3Eu7M65dtg0iLE3XF-zgw65J4mN26QOt-C62jl6zeg"
    st.write("[Peter, B. G., Cohen, S., Lucey, R., Munasinghe, D., Raney, A., & Brakenridge, G. R. (2020). Google Earth Engine Implementation of the Floodwater Depth Estimation Tool (FwDET-GEE) for rapid and large scale flood analysis. IEEE Geoscience and Remote Sensing Letters.](%s)" % url_3)
    st.write("This app has been developed by Chi-Hung Chang  & Son Do at University of Houston with supports from NASA SERVIR and GEOGloWS.")
    st.write("Kel Markert at SERVIR Coordination Office is also acknowledged for the development of this FIER-Mekong App.")
