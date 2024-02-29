"""
Optional module to define some useful ee functions related to Landsat images processing. 
"""
import ee, datetime, warnings
from typing import Union, Any, Dict, List, Literal, Callable

def scale_SR(img:ee.Image)->ee.Image:
    """Scales the optical and thermal bands (SR_B.* and ST_B.*)
    """
    # Scaling factors for Collection 02, level 2:
    opticalBands = img.select('SR_B.').multiply(0.0000275).add(-0.2)
    thermalBands = img.select('ST_B.*').multiply(0.00341802).add(149.0)

    return (img.addBands(opticalBands, overwrite=True)
        .addBands(thermalBands, overwrite=True)
    )

def cloud_mask(img: ee.Image, name:str ="cloud_cover") -> ee.Image:
    """Adds a "cloud_cover" band. 

    Requires a "QA_PIXEL" and "QA_RADSAT" band. 

    - 1: cloud
    - 0: not cloud
    - masked: L7 stripes or outside of the image. 

    See also: update_cloud_mask

    """
    qa_mask = img.select('QA_PIXEL').bitwiseAnd(int('11111',2)).neq(0)
    saturation_mask = img.select('QA_RADSAT').neq(0)
    cloud_mask=qa_mask.max(saturation_mask).rename(name) 
    return img.addBands(cloud_mask)


def cfmask(bandNames:list)->Callable:
    def apply_mask(img:ee.Image)->ee.Image:
        """Returns img with the cloud mask used to 
        update the mask on selected bands (bandNames)
        Requires bands: cloud_cover
        """
        cloud_mask = ee.Image(1).subtract(img.select("cloud_cover"))
        imgBands = (img.select(bandNames)
        .updateMask(cloud_mask)
        )
        return img.addBands(imgBands, overwrite=True)

    return apply_mask


def set_index(img: ee.Image) -> ee.Image:
    return img.set({'LANDSAT_INDEX':img.get('system:index'),
        'LANDSAT_FOOTPRINT': img.get('system:footprint')})


def add_ndvi(img:ee.Image)->ee.Image:
    """Adds NDVI to a Landsat 7*, 8, or 9 image. 
    *Bands are renamed in place to match Landsat 8/9, but not returned. 
    bands: nir, red
    """
    band_names = ["SR_B5", "SR_B4"] 
    bands_l7 = ["SR_B4", "SR_3"]
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    sel_bands = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),bands_l7, band_names)
    ndvi = (img.select(sel_bands, band_names)
            .normalizedDifference(band_names)
            .rename('NDVI'))
    return img.addBands(ndvi.clamp(-1,1))


def albedo_tasumi(img:ee.Image):
    """
    Tasumi et al (2008) albedo parameterization 

    Reference
    ---
    [Tasumi et al. (2008)](https://doi.org/10.1061/(ASCE)1084-0699(2008)13:2(51))
    [Ke et al. (2016)](https://doi.org/10.3390/rs8030215)

    """
    oli = '0.130*b("SR_B1") + 0.115*b("SR_B2") + 0.143*b("SR_B3") + 0.180*b("SR_B4") + 0.281*b("SR_B5") + 0.108*b("SR_B6") + 0.042*b("SR_B7")'
    etm = '0.254*b("SR_B1") + 0.149*b("SR_B2") + 0.147*b("SR_B3") + 0.311*b("SR_B4") + 0.103*b("SR_B5")                    + 0.036*b("SR_B7")'
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    expr = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),etm, oli)
    albedo = img.expression(expr).rename('albedo')
    return albedo


def add_albedo_tasumi(img:ee.Image)->ee.Image:
    """Adds albedo based on Tasumi et al. 2008 to a Landsat 7, 8, or 9 image.
    """
    alb = albedo_tasumi(img)
    return img.addBands(alb.clamp(0,1))


def albedo_liang(img:ee.Image, 
coefs=[0.356, 0.130, 0.373, 0.085, 0.072, -0.0018],
bands = ['SR_B2', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'])->ee.Image:
    """
    Liang (2001) albedo parameterization 
    for Landsat data: 
    0.356*blue + 0.130*red + 0.373*nir + 0.085*swir + 0.072*swir2 - 0.0018

    Optional inputs (defaults to Landsat-8 coefficients and band names*):
    coefs: 6 coefficients for a Landsat sensor
    bands: names of the bands in the Landsat ee.Image
        (corresponding to the blue, red, nir, swir, and swir2 bands)

    *for collection 02, level 2 (SR) product. 

    see also albedo_liang_vis, albedo_liang_nir

    Reference
    ---
    https://www.sciencedirect.com/science/article/pii/S0034425700002054

    """
    bblue = img.select(bands[0]).multiply(coefs[0])
    bred = img.select(bands[1]).multiply(coefs[1])
    bnir = img.select(bands[2]).multiply(coefs[2])
    bswir = img.select(bands[3]).multiply(coefs[3])
    bswir2 = img.select(bands[4]).multiply(coefs[4])
    albedo = bblue.add(bred).add(bnir).add(bswir).add(bswir2).add(coefs[5])
    albedo = albedo.rename('albedo')
    return albedo

def add_albedo_liang(img:ee.Image)->ee.Image:
    """Adds shortwave albedo (Liang, 2000) to a Landsat 7*, 8, or 9 image. 
    *Bands are renamed in place to match Landsat 8/9, but not returned. 
    bands: blue, red, nir, swir, swir2
    """
    band_names=['SR_B2', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    bands_l7=['SR_B1', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    sel_bands = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),bands_l7, band_names)
    alb = albedo_liang(img.select(sel_bands, band_names)).rename("albedo")
    return img.addBands(alb.clamp(0,1))

def add_rad_temp(img:ee.Image)->ee.Image:
    """Adds the "radiometric_temperature" band to a Landsat 7*, 8, or 9 image. 
    *Bands are renamed in place to match Landsat 8/9, but not returned. 
    bands: surface temperature
    """
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    thermal_band = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),"ST_B6", "ST_B10")
    return img.addBands(img.select([thermal_band], ["ST_B10"])
                        .rename("radiometric_temperature"))


def add_lai_loglinear(img:ee.Image)->ee.Image:
    """Adds a leaf area index (LAI*) band to a Lansdat image (requires NDVI band). 

    * "log-linear" method (e.g., Fisher et al., 2008):
        LAI = (-ln(1-fIPAR)/kPAR where fIPAR=1-0.05*NDVI) 

    Note: LAI is clamped to (0,7)
    """
    from geeet.vegetation import compute_lai
    lai = compute_lai(img.select("NDVI")).rename("LAI")
    return img.addBands(lai.clamp(0,7))


def add_lai_houborg2018(img:ee.Image)->ee.Image:
    """Adds a leaf area index (LAI**) band to a Landsat 7*, 8, or 9 image. 
    *Bands are renamed in place to match Landsat 8/9, but not returned. 

    ** "houborg2018" multi-vegetation index method (Houborg et al., 2018):

    Rule 1 (MSR <= 1.1384):
    LAI = -1.852 - 0.456 SR + 2.45 NDVI + 15.87 NDVI^2 + 0.8 EVI2 + 31.56 EVI2^2
        - 3.64 OSAVI - 36.35 OSAVI^2 + 1.5 EVI - 3.3 EVI^2 + 3.8 MSR
        - 4.38 NDWI - 5.96 NDWI^2 - 0.38 NDWI2 + 0.27 NDWI2^2
    
    Rule 2 (MSR > 1.1384):
    LAI = 3.061 - 0.004 SR + 87.32 NDVI - 19.65 NDVI^2 + 94.43 EVI2 - 29.5 EVI2^2
        - 172.66 OSAVI + 38.7 OSAVI^2 - 0.87 EVI - 2.95 EVI^2 + 3.45 MSR
        - 5.34 NDWI - 2.35 NDWI^2 - 18.08 NDWI2 + 14.54 NDWI2^2  

    Note: LAI is clamped to (0,7)
    """
    from geeet.vegetation import lai_houborg2018
    band_names=['SR_B2', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    bands_l7=['SR_B1', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    sel_bands = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),bands_l7, band_names)
    img_renamed = img.select(sel_bands, band_names) 
    lai = (lai_houborg2018(
        blue = img_renamed.select("SR_B2"),
        red  = img_renamed.select("SR_B4"),
        nir  = img_renamed.select("SR_B5"),
        swir1= img_renamed.select("SR_B6"), 
        swir2= img_renamed.select("SR_B7"),
        ).rename("LAI")
    )
    return img.addBands(lai.clamp(0,7))

def collection(
    date_start: Union[datetime.datetime, ee.Date, int, str, Any],
    date_end: Union[datetime.datetime, ee.Date, int, str, Any],
    region: Union[Dict[str, Any], ee.Geometry],
    sat_list:List[str] = ["LANDSAT_7", "LANDSAT_8", "LANDSAT_9"],
    max_cc:Union[int, float] = None,        
    exclude_pr:bool = None,
    include_pr:bool = None,
    ndvi = True,
    albedo:Union[None, Literal["liang2001", "tasumi2008"]] = "liang2001", 
    rad_temp = True,
    cfmask = True, 
    lai:Union[None,Literal["log-linear", "houborg2018"]]=None,
)-> ee.ImageCollection:
    """Prepares a merged landsat collection

    Includes LE07, LC08, and LC09 collection 02 level 2 products.

    - Filters the collections to the specified date range and region. 
    - Scaling factors are applied to optical (SR_*) and thermal (ST_*) bands. 
    - Optionally includes additional albedo, NDVI, radiometric_temperature, cloud_cover*, and LAI bands. 

    Does not apply cloud mask; use `cfmask` to create a mappable function.

    Args: 
        date_start: The start date to retrieve the data (see ee.Date)
        date_end: The end date to retrieve the data (see ee.Date)
        region: The region of interest (see ee.ImageCollection.filterBounds)
        sat_list: A list, subset of ["LANDSAT_7", "LANDSAT_8", "LANDSAT_9"] but not empty.
        Indicates which satellites to include in the image collection.
        exclude_pr: A list of path/rows to exclude given as a list. E.g.: [[170,40]] will exclude PATH/ROW 170040
        include_pr: A list of path/rows to include given as a list. Any path/row not included here will be excluded.
        ndvi: Include NDVI as an additional band, using the NIR and Red bands. Defaults to True. 
        albedo: None, "liang2001", or "tasumi2008":

            * None: do not include albedo
            * "liang2001": Include albedo as an additional band based on Liang et al. 2001
            * "tasumi2008": Include albedo as an additional band based on Tasumi et al. 2008
            
        rad_temp: Include radiometric_temperature (e.g., required for TSEB) as an additional band. Defaults to True. 
        cfmask: Include cloud_cover as an additional band. Defaults to True. 
        lai: None, "log-linear", or "houborg2018":
        
            * None: do not include LAI
            * "log-linear": Include LAI as an additional band using the NDVI-based relationship as in 
                PT-JPL (Fisher et al., 2008): LAI=(-ln(1-fIPAR)/kPAR where fIPAR=1-0.05*NDVI).
                NDVI will be included even if ndvi is set to False.  
            * "houborg2018": Include LAI as an additional band using the multi-spectral rule-based
                relationship from Houborg et al., 2018
        
    Returns: ee.ImageCollection
    """
    import ee
    from .parsers import feature_collection

    region = feature_collection(region)

    filter_collection = ee.Filter.And(
        ee.Filter.bounds(region),
        ee.Filter.date(date_start, date_end)
    )
    L7_collection = (
        ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
        .filter(filter_collection)
        .map(set_index)
    )
    L8_collection = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filter(filter_collection)
        .map(set_index)
    )
    L9_collection = (
        ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
        .filter(filter_collection)
        .map(set_index)
    )

    collection = (L7_collection.merge(L8_collection)
    .merge(L9_collection)
    .filter(ee.Filter.inList("SPACECRAFT_ID", ee.List(sat_list))))
    
    if max_cc:
        collection = collection.filter(ee.Filter.lte("CLOUD_COVER", max_cc))

    if exclude_pr is not None:
        collection = collection.filter(ee.Filter.Or([
                ee.Filter.And(
                    ee.Filter.eq("WRS_PATH", pr[0]),
                    ee.Filter.eq("WRS_ROW", pr[1]))
            for pr in exclude_pr])
            .Not())

    if include_pr is not None:
         collection = collection.filter(ee.Filter.Or([
                ee.Filter.And(
                    ee.Filter.eq("WRS_PATH", pr[0]),
                    ee.Filter.eq("WRS_ROW", pr[1]))
            for pr in include_pr])
            )       

    collection = collection.map(scale_SR)

    if(ndvi):
        collection = collection.map(add_ndvi)

    if albedo is not None:
        if albedo=="liang2001":
            collection = collection.map(add_albedo_liang)
        if albedo=="tasumi2008":
            collection = collection.map(add_albedo_tasumi)

    if(rad_temp):
        collection = collection.map(add_rad_temp)

    if(cfmask):
        collection = collection.map(cloud_mask)

    if lai is not None:
        if lai=="log-linear":
            if not ndvi:
                collection = collection.map(add_ndvi)
            collection = collection.map(add_lai_loglinear)

        if lai=="houborg2018":
            collection = collection.map(add_lai_houborg2018)

    return collection


def geesebal_compatibility(img:ee.Image)->ee.Image:
    """
    Mappable function to ensure compatibility with geeSEBAL (expects Landsat C01).
    """
    # geeSEBAL expects B, GR, R, NIR, SWIR_1, SWIR_2 bands 
    # with the C01 scale (1/10000) 
    band_names = ["B", "GR", "R", "NIR", "SWIR_1", "SWIR_2"]
    oli_names = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
    etm_names = ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"]
    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    sel_bands = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),etm_names, oli_names)
    normalized = img.select(sel_bands).rename(band_names).multiply(10000)  

    return (img
        # geeSEBAL expects the T_RAD band in W/(m^2*sr*um)/DN
        .addBands(img.select("ST_TRAD").multiply(0.001).rename("T_RAD")) 
        .addBands(img.select("albedo").rename("ALFA"))   # geesebal expects ALFA
        # geeSEBAL expects BRT with the C01 scale (1/10)
        .addBands(img.select("radiometric_temperature").multiply(10).rename("BRT"))  # geesebal expects BRT (ST_B6 | ST_B10)
        .addBands(normalized) # SR_* bands
        # geeSEBAL expects SOLAR_ZENITH_ANGLE (C01) -- not available in C02 (SUN_ELEVATION instead)
        # and SATELLITE (renamed to SPACECRAFT_ID in C02)
        .set({
            "SOLAR_ZENITH_ANGLE": ee.Number(90).subtract(img.get("SUN_ELEVATION")),
            "SATELLITE": img.get("SPACECRAFT_ID"),
        })
    )

def albedo_liang_vis(img,
coefs = [0.443, 0.317, 0.240],
bands = ['SR_B2', 'SR_B3', 'SR_B4']):
    """
    Liang (2001) albedo (visible) parameterization
    see albedo_liang
    """
    bblue = img.select(bands[0]).multiply(coefs[0])
    bgreen = img.select(bands[1]).multiply(coefs[1])
    bred = img.select(bands[2]).multiply(coefs[2])
    albedo = bblue.add(bgreen).add(bred)
    return albedo.rename('albedo_vis')

def albedo_liang_nir(img,
coefs = [0.693, 0.212, 0.116, -0.003],
bands = ['SR_B5', 'SR_B6', 'SR_B7']):
    """
    Liang (2001) albedo (nir) parameterization
    see albedo_liang
    """
    bnir = img.select(bands[0]).multiply(coefs[0])
    bswir = img.select(bands[1]).multiply(coefs[1])
    bswir2 = img.select(bands[2]).multiply(coefs[2])
    albedo = bnir.add(bswir).add(bswir2).add(coefs[3])
    return albedo.rename('albedo_nir')

# DEPRECATED:
def constrain_range(img):
    """
    Constrain range to 0-1 for
    a single band image
    """
    img = img.min(1)
    img = img.max(0)
    return img

def constrain_range_lai(img):
    """
    Constrain range to 0-7 for
    a single band image
    """
    img = img.min(7)
    img = img.max(0)
    return img

def update_cloud_mask(img: ee.Image) -> ee.Image:
    """
    Quality bit-based cloud/cloud-shadow mask for
    a Landsat Collection 02 ee.Image (either TOA or SR)
    Input: img (ee.Image)

    See also: cloud_mask (adds cloud_cover band)
    """
    warnings.warn(
                    "update_cloud_mask is deprecated. "
                    "Use `landsat.cloud_mask` and `landsat.cfmask` instead.",
                    FutureWarning
                )
    # mask if QA_PIXEL has any of the 0,1,2,3,4 bits on
    # which correspond to: Fill, Dilated Cloud, Cirurs, Cloud, Cloud shadow
    # i.e. we want to keep pixels where the bitwiseAnd with 11111 is 0:
    qa_mask = img.select('QA_PIXEL').bitwiseAnd(int('11111',2)).eq(0)
    # Mask any over-saturated pixel as well: 
    saturation_mask = img.select('QA_RADSAT').eq(0)
    return img.updateMask(qa_mask).updateMask(saturation_mask)


def l8c02_add_inputs(img):
    """
    Adds the "albedo", "NDVI", "LAI", and "radiometric_temperature" bands
    Originaly built for Landsat 8 (Collection 02) images, 
    useful as is for Landsat 9 images
    Updated to work with Landsat 7 images as well
    (by simply renaming the bands on the fly)

    Albedo: shortwave albedo using the empirical coefficients of Liang (2001)
    LST: ST_B10 for "radiometric_temperature" 
    LAI: Houborg and McCabe (2018) cubist hybrid trained model
    """
    import ee
    from geeet.vegetation import lai_houborg2018, compute_lai

    warnings.warn(
                    "l8c02_add_inputs is deprecated. "
                    "Use `landsat.collection` instead.",
                    FutureWarning
                )

    # blue, green, red, nir, swir1, swir2, thermal:
    bands_l8 = ee.List(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'ST_B10'])
    bands_l7 = ee.List(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'ST_B6'])

    spacecraft_id = ee.String(img.get('SPACECRAFT_ID'))
    bands = ee.Algorithms.If(spacecraft_id.equals('LANDSAT_7'),
    bands_l7,
    bands_l8)

    img_renamed = img.select(bands, bands_l8) 
    # ^^ force band names to l8 names

    albedo = albedo_liang(img_renamed)
    albedo = constrain_range(albedo)
    albedo_vis = albedo_liang_vis(img_renamed)
    albedo_vis = constrain_range(albedo_vis)
    albedo_nir = albedo_liang_nir(img_renamed)
    albedo_nir = constrain_range(albedo_nir)
    ndvi = img_renamed.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    lst = img_renamed.select('ST_B10').rename('radiometric_temperature')

    # Lai - Houborg 2018 cubist trained model:
    bands = ['SR_B2', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    blue = img_renamed.select(bands[0])
    red = img_renamed.select(bands[1])
    nir = img_renamed.select(bands[2])
    swir1 = img_renamed.select(bands[3])
    swir2 = img_renamed.select(bands[4])
    
    #lai = compute_lai(ndvi)  # simple model
    lai = lai_houborg2018(
        blue = blue, red = red, nir = nir, swir1=swir1, swir2=swir2
    ).rename('LAI')
    lai = constrain_range_lai(lai)
    return img.addBands(albedo).addBands(albedo_vis).addBands(albedo_nir)\
        .addBands(ndvi).addBands(lst).addBands(lai)