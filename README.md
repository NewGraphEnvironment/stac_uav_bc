
<!-- README.md is generated from README.Rmd. Please edit that file -->

# stac_uav_bc

![groovy](https://img.shields.io/badge/status-groovy-gren)
![fUn](https://img.shields.io/badge/plays-fUn-red)

The goal of `stac_uav_bc` is to document and serve out our UAV
collection for British Columbia. It is organized by watershed and can be
queried by location and time using our API via the lovely [`rstac` R
package](https://brazil-data-cube.github.io/rstac/) and [QGIS
(v3.42+)](https://qgis.org/). Still a work in progress but currently
functioning.

<img src="fig/cover.JPG" width="100%" style="display: block; margin: auto;" />

<br>

<div style="text-align: center; font-weight: bold; margin-bottom: 10px;">

Drone imagery download and viewer links. <b>NOTE: Links to viewer
current may need to be manually altered in browser to begin with http vs
https! This should be resolved soon.</b>

</div>

As of QGIS 3.42 - ONE can also access stac items (orthoimagery, Digital
Surface Models and Digital Terrain Models in our case) directly via the
Data Source Manager. See a blog with details
[here](https://www.lutraconsulting.co.uk/blogs/stac-in-qgis). It looks
like this in the th `Layer / Data Source Manager` toolbar in QGIS:

<img src="fig/a11sone01.png" width="100%" />

<img src="fig/a11sone02.png" width="100%" />
