
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

``` r
fpr::fpr_photo_resize_convert("fig/cover.png", path = "fig")
knitr::include_graphics("fig/cover.JPG")
```

<img src="fig/cover.JPG" width="100%" style="display: block; margin: auto;" />

This a bounding box for the [Neexdzi
Kwa](https://www.newgraphenvironment.com/restoration_wedzin_kwa_2024/)
watershed (aka - the Upper Bulkley River near Houston BC)

``` r
q <- rstac::stac("http://www.a11s.one:8000/") |>
  rstac::stac_search(collections = "uav-imagery-bc",
                     bbox = c(-126.77000, 54.08832, -125.88822, 54.68786)) |>
  rstac::post_request()

q |>
  rstac::items_fetch()
```

    ## ###Items
    ## - features (32 item(s)):
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_dem-dtm
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_dem-dsm
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_dem-dtm
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_dem-dsm
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_dem-dtm
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_dem-dsm
    ##   - skeena-bulkley-2024-bulkley-mckilligan-barren-ortho
    ##   - ... with 22 more feature(s).
    ## - assets: image
    ## - item's fields: assets, bbox, collection, geometry, id, links, properties, stac_extensions, stac_version, type

``` r
q <- rstac::stac("http://www.a11s.one:8000/") |>
  rstac::stac_search(collections = "uav-imagery-bc",
                     bbox = c(-126.77000, 54.08832, -125.88822, 54.68786)) |>
  rstac::post_request()

q |>
  rstac::items_fetch()
```

    ## ###Items
    ## - features (32 item(s)):
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_dem-dtm
    ##   - skeena-bulkley-2021-197912_roberthatch-odm_dem-dsm
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_dem-dtm
    ##   - skeena-bulkley-2021-197662_richfield_hwy16-odm_dem-dsm
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_orthophoto-odm_orthophoto
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_dem-dtm
    ##   - skeena-bulkley-2024-bulkley-wilson01-odm_dem-dsm
    ##   - skeena-bulkley-2024-bulkley-mckilligan-barren-ortho
    ##   - ... with 22 more feature(s).
    ## - assets: image
    ## - item's fields: assets, bbox, collection, geometry, id, links, properties, stac_extensions, stac_version, type

As of QGIS 3.42 can also access stac items (orthoimagery, Digital
Surface Models and Digital Terrain Models in our case) directly now via
QGIS. See a blog with details about that
[here](https://www.lutraconsulting.co.uk/blogs/stac-in-qgis). It looks
like this in the th `Layer / Data Source Manager` toolbar in QGIS:

``` r
knitr::include_graphics("fig/a11sone01.png")
```

<img src="fig/a11sone01.png" width="1922" />

``` r
knitr::include_graphics("fig/a11sone02.png")
```

<img src="fig/a11sone02.png" width="1922" />

``` r
rmarkdown::render("README.Rmd", output_format = "github_document")
rmarkdown::render("README.Rmd", output_format = "html_document")
```
