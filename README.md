# geeet


[![image](https://img.shields.io/pypi/v/geeet.svg)](https://pypi.python.org/pypi/geeet)
[![image](https://img.shields.io/conda/vn/conda-forge/geeet.svg)](https://anaconda.org/conda-forge/geeet)
[![image](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Evapotranspiration (ET) models for use in python and with integration into Google Earth Engine.**

geeet aims to provide users with hybrid evapotranspiration (ET) models that run with numerical values and with Google Earth Engine images. 

- GitHub repo: https://github.com/kaust-halo/geeet
- PyPI: https://pypi.org/project/geeet/
- Conda-forge: https://anaconda.org/conda-forge/geeet
- Free software: MIT license

## Features

This initial release features a PT-JPL model adapted for arid environments (as described in Aragon et al., 2018). A notebook example is included [here](./examples/notebooks/01_PTJPL.ipynb). 

### PT-JPL model for arid environments (as described in [Aragon et al., 2018](http://dx.doi.org/10.3390/rs10121867))   

To run the PT-JPL model (arid environments) for a single site, run:

```python
from geeet.ptjpl import ptjpl_arid
ET = ptjpl_arid(RH=25.3, Temp_C=24.3442, Press=94.524, Rn=374.8117, NDVI=0.7588, F_aparmax=0.7295, doy=105, time = 11, longitude = 38.4381)  
# eot_params: Day of year, time, longitude, standard meridian
```

To run the same model using a *Google Earth Engine image*, run:

```python
from geeet.ptjpl import ptjpl_arid
ET = ptjpl_arid(img)
```
where img is a `ee.Image` and all required inputs are given as bands within `img`.  

For more information, see the [notebook example](./examples/notebooks/01_PTJPL.ipynb). 

This function can also be mapped to an `ee.ImageCollection`:

```python
from geeet.ptjpl import ptjpl_arid
et_outputs = et_inputs.map(ptjpl_arid)
```
where `et_inputs` is an `ee.ImageCollection` with the required inputs (see the [notebook example](./examples/notebooks/02_PTJPL_collection.ipynb)). 

## Installation

`pip install geeet`

or

`conda install -c conda-forge geeet`

## References

References for each model are found in [REFERENCES.txt](REFERENCES.txt). The source code for each module contains references for each function as well. Finally, each model contains two functions to display the references: `cite()` shows the main citation for the model, while `cite_all()` shows all the references for that model.

If you use this package for research, please cite the relevant model. 

## Contributions

Contributions are welcome. We aim to include as many ET models to allow researchers to intercompare the different models. 

## Credits

This package was created with [Cookiecutter](https://github.com/cookiecutter/cookiecutter) and the [giswqs/pypackage](https://github.com/giswqs/pypackage) project template.
