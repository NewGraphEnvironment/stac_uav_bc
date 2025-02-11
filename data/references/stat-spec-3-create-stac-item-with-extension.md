Create a STAC Item that Implements the Extensions Using PySTAC¶
In this tutorial, you will learn how to add more information to a STAC Item using STAC Extensions.

In the previous tutorial, you created a STAC Item and added it to a STAC Catalog. The item you created only implemented the core STAC Item specification.

What is a STAC Extension?¶
With extensions, we can provide additional metadata or features related to specific types of geospatial data or specialized use cases.

For instance, beyond just identifying what an image represents, an extension could indicate the estimated cloud cover, sun elevation, resolution, and other distinct attributes. This granularity not only aids users in pinpointing the exact data they need but also assists developers in comprehensively describing multiple datasets.

This tutorial builds off of the knowledge from the previous tutorial. Let's create an item that utilizes a few common STAC Extensions:

the Electro-Optical (EO) Extension
the View Extension
the Projection Extension
We will continue to use the data from the previous tutorial and will add the item we create into the STAC Catalog you just created.

Given that we know the tiff image we are working with is a WorldView-3 image that has earth observation data, we can enhance our items metadata using several STAC Extensions. We'll enable the EO Extension to add detailed band information. Additionally, we are using the View Extension and the Projection Extension to incorporate properties such as sun_azimuth, sun_elevation, and the EPSG code of the data.

Dependencies¶
If you need to install pystac, rasterio, or pystac, uncomment the lines below and run the cell.

In [ ]:
# ! pip install pystac
# ! pip install rasterio
# ! pip install shapely
Import Packages and Store Data¶
To begin, import the packages and classes that you need to access data and work with STAC Items in Python.

In [2]:
import os
import rasterio
import urllib.request
import pystac

from shapely.geometry import Polygon, mapping
from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from pystac.extensions.eo import Band, EOExtension
from pystac.extensions.view import ViewExtension
from pystac.extensions.projection import ProjectionExtension
Just like in the previous tutorial, we will set up a temporary directory and store the same image in it.

In [3]:
# Set the temporary directory to store source data
tmp_dir = TemporaryDirectory()
img_path = os.path.join(tmp_dir.name, 'image.tif')

# Fetch and store data
url = ('https://spacenet-dataset.s3.amazonaws.com/'
       'spacenet/SN5_roads/train/AOI_7_Moscow/MS/'
       'SN5_roads_train_AOI_7_Moscow_MS_chip996.tif')
urllib.request.urlretrieve(url, img_path)
Out[3]:
('/var/folders/wr/1r7t95ls0gd9j15m9f1gc7_80000gp/T/tmph43hcw0r/image.tif',
 <http.client.HTTPMessage at 0x1171f2df0>)
Define the Bands of WorldView-3¶
To add the EO information to an item we'll need to specify some more data. First, let's define the bands of WorldView-3. We have collected this band information from the WorldView-3 Data Sheet.

In [4]:
wv3_bands = [Band.create(name='Coastal', description='Coastal: 400 - 450 nm', common_name='coastal'),
             Band.create(name='Blue', description='Blue: 450 - 510 nm', common_name='blue'),
             Band.create(name='Green', description='Green: 510 - 580 nm', common_name='green'),
             Band.create(name='Yellow', description='Yellow: 585 - 625 nm', common_name='yellow'),
             Band.create(name='Red', description='Red: 630 - 690 nm', common_name='red'),
             Band.create(name='Red Edge', description='Red Edge: 705 - 745 nm', common_name='rededge'),
             Band.create(name='Near-IR1', description='Near-IR1: 770 - 895 nm', common_name='nir08'),
             Band.create(name='Near-IR2', description='Near-IR2: 860 - 1040 nm', common_name='nir09')]
Notice that we used the .create method to create new band information.

Collect the Item's geometry and bbox¶
To get the bounding box and footprint of the image, we will utilize the get_bbox_and_footprint function we first used in the Create a STAC Catalog Tutorial.

In [5]:
def get_bbox_and_footprint(raster):
    with rasterio.open(raster) as r:
        crs = r.crs
        bounds = r.bounds
        bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        footprint = Polygon([
            [bounds.left, bounds.bottom],
            [bounds.left, bounds.top],
            [bounds.right, bounds.top],
            [bounds.right, bounds.bottom]
        ])
        
        return (bbox, mapping(footprint),crs)
In [6]:
bbox, footprint,crs = get_bbox_and_footprint(img_path)
In [7]:
item = pystac.Item(id='local-image-eo',
                      geometry=footprint,
                      bbox=bbox,
                      datetime=datetime.utcnow(),
                      properties={})
In [8]:
item
Out[8]:
type "Feature"
stac_version "1.0.0"
id "local-image-eo"
properties
geometry
links [] 0 items
assets
bbox [] 4 items
stac_extensions [] 0 items
In the above output, we can see no additional attributes has added.

EO Extension¶
We can add given fields in the item using EO extension and this enables more filter to client.

EO Extension fields

We can now create an item, enable the EO Extension, add the band information and add it to our catalog.

In [9]:
eo = EOExtension.ext(item, add_if_missing=True)
eo.apply(bands=wv3_bands)
There are also common metadata fields that we can use to capture additional information about the WorldView-3 imagery:

In [10]:
item.common_metadata.platform = "Maxar"
item.common_metadata.instruments = ["WorldView3"]
item.common_metadata.gsd = 0.3
In [11]:
item
Out[11]:
type "Feature"
stac_version "1.0.0"
id "local-image-eo"
properties
geometry
links [] 0 items
assets
bbox [] 4 items
stac_extensions [] 1 items
We can use the EO Extension to add bands to the assets we add to the item:

In [12]:
asset = pystac.Asset(href=img_path, 
                     media_type=pystac.MediaType.GEOTIFF)
item.add_asset("image", asset)
eo_on_asset = EOExtension.ext(item.assets["image"])
eo_on_asset.apply(wv3_bands)
If we look at the asset's JSON representation, we can see the appropriate band indexes are set:

In [13]:
asset.to_dict()
Out[13]:
{'href': '/var/folders/wr/1r7t95ls0gd9j15m9f1gc7_80000gp/T/tmph43hcw0r/image.tif',
 'type': <MediaType.GEOTIFF: 'image/tiff; application=geotiff'>,
 'eo:bands': [{'name': 'Coastal',
   'common_name': 'coastal',
   'description': 'Coastal: 400 - 450 nm'},
  {'name': 'Blue', 'common_name': 'blue', 'description': 'Blue: 450 - 510 nm'},
  {'name': 'Green',
   'common_name': 'green',
   'description': 'Green: 510 - 580 nm'},
  {'name': 'Yellow',
   'common_name': 'yellow',
   'description': 'Yellow: 585 - 625 nm'},
  {'name': 'Red', 'common_name': 'red', 'description': 'Red: 630 - 690 nm'},
  {'name': 'Red Edge',
   'common_name': 'rededge',
   'description': 'Red Edge: 705 - 745 nm'},
  {'name': 'Near-IR1',
   'common_name': 'nir08',
   'description': 'Near-IR1: 770 - 895 nm'},
  {'name': 'Near-IR2',
   'common_name': 'nir09',
   'description': 'Near-IR2: 860 - 1040 nm'}]}
View Extension¶
It adds metadata related to angles of sensors and other radiance angles that affect the view of resulting data.

View Extension fields

Here we are adding manually the field values, but how to extract from Landsat metadata follow this tutorial.

In [14]:
view_ext = ViewExtension.ext(item, add_if_missing=True)
view_ext.sun_azimuth = 160.86021018
view_ext.sun_elevation = 23.81656674
In [15]:
item.properties
Out[15]:
{'datetime': '2023-10-16T09:08:53.705550Z',
 'eo:bands': [{'name': 'Coastal',
   'common_name': 'coastal',
   'description': 'Coastal: 400 - 450 nm'},
  {'name': 'Blue', 'common_name': 'blue', 'description': 'Blue: 450 - 510 nm'},
  {'name': 'Green',
   'common_name': 'green',
   'description': 'Green: 510 - 580 nm'},
  {'name': 'Yellow',
   'common_name': 'yellow',
   'description': 'Yellow: 585 - 625 nm'},
  {'name': 'Red', 'common_name': 'red', 'description': 'Red: 630 - 690 nm'},
  {'name': 'Red Edge',
   'common_name': 'rededge',
   'description': 'Red Edge: 705 - 745 nm'},
  {'name': 'Near-IR1',
   'common_name': 'nir08',
   'description': 'Near-IR1: 770 - 895 nm'},
  {'name': 'Near-IR2',
   'common_name': 'nir09',
   'description': 'Near-IR2: 860 - 1040 nm'}],
 'platform': 'Maxar',
 'instruments': ['WorldView3'],
 'gsd': 0.3,
 'view:sun_azimuth': 160.86021018,
 'view:sun_elevation': 23.81656674}
Projection Extension¶
Here, we are specifying the EPSG code for the image manually, but PySTAC can also figure out the correct EPSG code. Check out this tutorial to see how.

Projection Extension fields

In [16]:
proj_ext = ProjectionExtension.ext(item, add_if_missing=True)
proj_ext.epsg = 4326
In [17]:
item.properties
Out[17]:
{'datetime': '2023-10-16T09:08:53.705550Z',
 'eo:bands': [{'name': 'Coastal',
   'common_name': 'coastal',
   'description': 'Coastal: 400 - 450 nm'},
  {'name': 'Blue', 'common_name': 'blue', 'description': 'Blue: 450 - 510 nm'},
  {'name': 'Green',
   'common_name': 'green',
   'description': 'Green: 510 - 580 nm'},
  {'name': 'Yellow',
   'common_name': 'yellow',
   'description': 'Yellow: 585 - 625 nm'},
  {'name': 'Red', 'common_name': 'red', 'description': 'Red: 630 - 690 nm'},
  {'name': 'Red Edge',
   'common_name': 'rededge',
   'description': 'Red Edge: 705 - 745 nm'},
  {'name': 'Near-IR1',
   'common_name': 'nir08',
   'description': 'Near-IR1: 770 - 895 nm'},
  {'name': 'Near-IR2',
   'common_name': 'nir09',
   'description': 'Near-IR2: 860 - 1040 nm'}],
 'platform': 'Maxar',
 'instruments': ['WorldView3'],
 'gsd': 0.3,
 'view:sun_azimuth': 160.86021018,
 'view:sun_elevation': 23.81656674,
 'proj:epsg': 4326}
Let's create a catalog, add the item that uses our extensions (EO, View, and Projection), and save to a new STAC.

In [27]:
catalog = pystac.Catalog(id='tutorial-catalog', 
                         description='This Catalog is a basic demonstration Catalog to teach the use of the extensions.')
In [19]:
catalog.add_item(item)
list(catalog.get_items())
Out[19]:
[<Item id=local-image-eo>]
In [20]:
catalog.normalize_and_save(root_href=os.path.join(tmp_dir.name, 'stac-extension'), 
                           catalog_type=pystac.CatalogType.SELF_CONTAINED)
Now, if we read the catalog from the file system, PySTAC recognizes that the item implements some extensions and uses their functionality.

In [21]:
catalog2 = pystac.read_file(os.path.join(tmp_dir.name, 'stac-extension', 'catalog.json'))
In [22]:
assert isinstance(catalog2, pystac.Catalog)
list(catalog2.get_items())
Out[22]:
[<Item id=local-image-eo>]
In [23]:
item: pystac.Item = next(catalog2.get_all_items())
In [24]:
assert EOExtension.has_extension(item)
Below, we can see the bands of the asset from the information in the eo extension

In [25]:
eo_on_asset = EOExtension.ext(item.assets["image"])
print(eo_on_asset.bands)
[<Band name=Coastal>, <Band name=Blue>, <Band name=Green>, <Band name=Yellow>, <Band name=Red>, <Band name=Red Edge>, <Band name=Near-IR1>, <Band name=Near-IR2>]
Cleanup¶
Don't forget to clean up the temporary directory.

In [26]:
tmp_dir.cleanup()
Now you have created an Item with a few popular STAC Extensions. In the following tutorial, you will learn how to add a Collection to this STAC Catalog.