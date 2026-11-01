GENERAL INFORMATION

G01. Dataset version 3.1.1
G02. Name of the dataset: River flood hazard maps for Europe and the Mediterranean Basin region 
G03. Description of the dataset: River flood hazard maps for Europe and the Mediterranean Basin region is a gridded data set representing inundation along the river network, for nine different flood return periods. The input river flow data for the new maps are produced by means of the open-source hydrological model LISFLOOD, while inundation simulations are performed with the hydrodynamic model LISFLOOD-FP. 
G04. Creator of data set: Copernicus Emergency Management Service
G05. DOI of dataset: https://doi.org/10.2905/1D128B6C-A4EE-4858-9E34-6210707F3C81
G06. PID of dataset: http://data.europa.eu/89h/1d128b6c-a4ee-4858-9e34-6210707f3c81
G07. Keywords (author defined): flood, hazard, map, pan-European, Mediterranean
G08. Language(s) used in the dataset: English
G09. Last update of the README file: 05.03.2026

DATA DESCRIPTION

D01. Horizontal coverage: European extended domain (-24.54, 67.26; 27.81, 71.13) 
D02. Horizontal resolution: 3 arc seconds (~90 m)
D03. Spatial gaps: Only land areas are covered by this data set
D04. Temporal coverage: NA
D05. Temporal resolution: NA
D06. Temporal gaps: NA
D07. Number of available variables: 1 (flood water depth)
D08. Variables available at daily resolution: NA
D09. Variables available at 6-hourly resolution: NA
D10. Units: meters
D11. Update frequency: irregular
D12. Projection: wgs_1984
D13. Data type: 3 arc seconds (~90m) grid
D14. Available version(s): 3

PROJECT INFORMATION

P01. Project information: River flood hazard maps for Europe and the Mediterranean Basin region have been produced as part of the European Flood Awareness System (EFAS) of the Copernicus Emergency Management Service.
P02. Project website: https://emergency.copernicus.eu/
P03. Project funder: European Commission

FILE OVERVIEW

F01. Number of files described by the README-file: 11 
F02. The different files represent: (i) the flood hazard maps for different return periods; (ii) the permanent water bodies used to patch the flood hazard maps; (iii) and the spurious depth map that identifies areas where depths >10m are predicted in small channels (<3,000km^2) for the 10-year return period, plus a 2km buffer. Note that very high water depths may be caused by limitations in the hydraulic model in combination with the spatial resolution or by artificial sinks in the DEM. Users should exercise caution when using the depth values in these areas. 
F03. Naming conventions for file names: Europe_<RPXX-permanent_water_bodies><spurious_depth_areas>_filled_depth.tif 
F04. Explanation of abbreviations: RP = Return period, XX denotes the return period year; 
F05. File formats: Tagged Image File Format tif
F06. Software necessary to open the file: any software that opens tif, e.g. ArcGIS, QGIS etc.

STORAGE INFORMATION

S01. Where are the data stored?: JRC Data Store, https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/

DATA ACCESS AND SHARING

A01. Recommended citation for the dataset: Baugh, Calum; Colonese, Juan; D'Angelo, Claudia; Francesco, Dottori; Neal, Jeffrey; Prudhomme, Christel; Salamon, Peter. (2024): An updated dataset of global and European flood hazard maps. Manuscript under preparation.
A02. License information, restrictions on use: Open Data Commons Open Database License v1.0
A03. Copyright statement: https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/copyright.txt
A04. User support service: contact person outlined in the JRC Data Catalogue

RELATIONSHIPS

R01. Reference publication of this dataset: Baugh, Calum; Colonese, Juan; D'Angelo, Claudia; Francesco, Dottori; Neal, Jeffrey; Prudhomme, Christel; Salamon, Peter. (2024): An updated dataset of global and European flood hazard maps. Manuscript under preparation. 
R02. Mazzetti, C., Carton de Wiart, C., Gomes, G., Russo, C., Decremer, D., Ramos, A., Grimaldi, S., Disperati, J., Ziese, M., Schweim, C., Sanchez Garcia, R., Jacobson, T., Salamon, P., Prudhomme, C. (2023): River discharge and related historical data from the European Flood Awareness System, v5.0, European Commission, Joint Research Centre (JRC). https://doi.org/10.24381/cds.e3458969 
R03. This dataset incorporates the following other datasets: MERIT-DEM, MERIT-HYDRO, EFAS v5.0 hydrological reanalysis
