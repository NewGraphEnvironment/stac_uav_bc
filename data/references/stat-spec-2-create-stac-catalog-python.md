Language
en
STAC logo
TutorialsAboutGet Involved
STAC Tutorials
Getting Started
In the following tutorials, you will learn to add additional STAC components and functionality to the basic STAC Catalog you create here. The experience you gain from this tutorial along with the extensive PySTAC documentation will allow you to create your own STAC Catalog on a different dataset.

Dependencies¶
If you need to install pystac, rasterio, or pystac, uncomment the lines below and run the cell.

In [1]:
# ! pip install pystac
# ! pip install rasterio
# ! pip install shapely
Import Packages and Store Data¶
To begin, import the packages and classes that you need to access data and work with STAC Catalogs in Python.

In [2]:
import os
import json
import rasterio
import urllib.request
import pystac

from datetime import datetime, timezone
from shapely.geometry import Polygon, mapping
from tempfile import TemporaryDirectory
To give us some material to work with, let's download a single image from the SpaceNet 5 Challenge. We will use a temporary directory to save our single-Item STAC.

In [3]:
# Set temporary directory to store source data
tmp_dir = TemporaryDirectory()
img_path = os.path.join(tmp_dir.name, 'image.tif')

# Fetch and store data
url = ('https://spacenet-dataset.s3.amazonaws.com/'
       'spacenet/SN5_roads/train/AOI_7_Moscow/MS/'
       'SN5_roads_train_AOI_7_Moscow_MS_chip996.tif')
urllib.request.urlretrieve(url, img_path)
Out[3]:
('/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/image.tif',
 <http.client.HTTPMessage at 0x116ffa710>)
We want to create a STAC Catalog. Take a look at the Catalog documentation to see what information you need to create our PySTAC Catalog instance.

Create the STAC Catalog¶
Start by first creating the catalog and only populating the required arguments: the ID and description. The remaining arguments will be added to the catalog further along in the tutorial.

In [4]:
catalog = pystac.Catalog(id='tutorial-catalog', description='This catalog is a basic demonstration catalog utilizing a scene from SpaceNet 5.')
The catalog now exists. Take a look inside.

In the Introduction to STAC lesson on this site, you learned about the three main components of the STAC Specification and the possible relations between them all. Based on what you learned and what we have done so far, do you think your catalog has any children or items? Let's take a look:

In [5]:
print(list(catalog.get_children()))
print(list(catalog.get_items()))
[]
[]
Since we have not added them, there are no children or items in the catalog yet. We need to add these components.

JSON Progress Check¶
Throughout this tutorial, we will be checking in on the STAC components we are creating using to_dict() to see how the STAC JSON is shaping up. Let's take a look at the catalog we just created.

In [6]:
print(json.dumps(catalog.to_dict(), indent=4))
{
    "type": "Catalog",
    "id": "tutorial-catalog",
    "stac_version": "1.0.0",
    "description": "This catalog is a basic demonstration catalog utilizing a scene from SpaceNet 5.",
    "links": []
}
Create a STAC Item¶
Now that the catalog exists, we can populate it. Let's create a STAC Item to represent the image we saved in the temporary directory. Again, take a look at the PySTAC Documentation for an Item to see what you need to supply.

For creating this item, you will populate all the attributes at once.

Let's collect the information we need for each attribute.

Collect the Item's geometry and bbox¶
Using rasterio, we can extract the image's bounding box and geometry metadata.

In [7]:
def get_bbox_and_footprint(raster):
    with rasterio.open(raster) as r:
        bounds = r.bounds
        bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        footprint = Polygon([
            [bounds.left, bounds.bottom],
            [bounds.left, bounds.top],
            [bounds.right, bounds.top],
            [bounds.right, bounds.bottom]
        ])
        
        return (bbox, mapping(footprint))
In [8]:
# Run the function and print out the results
bbox, footprint = get_bbox_and_footprint(img_path)
print("bbox: ", bbox, "\n")
print("footprint: ", footprint)
bbox:  [37.6616853489879, 55.73478197572927, 37.66573047610874, 55.73882710285011] 

footprint:  {'type': 'Polygon', 'coordinates': (((37.6616853489879, 55.73478197572927), (37.6616853489879, 55.73882710285011), (37.66573047610874, 55.73882710285011), (37.66573047610874, 55.73478197572927), (37.6616853489879, 55.73478197572927)),)}
Collect the Item datetime¶
To obtain the datetime property for our Item from the image, we will use datetime.now().

In [9]:
datetime_utc = datetime.now(tz=timezone.utc)
Populate pystac.Item¶
In [10]:
item = pystac.Item(id='local-image',
                 geometry=footprint,
                 bbox=bbox,
                 datetime=datetime_utc,
                 properties={})
Now we have our first Item.

However, the item has not been added to our catalog yet. Therefore, when you run the following cell, you can see that the Item does not have a parent yet:

In [11]:
print(item.get_parent() is None)
True
Add the Item to the Catalog¶
In [12]:
catalog.add_item(item)
Out[12]:
rel "item"
href None
type "application/json"
Visualize the Catalog Relationship¶
Now that we have added the item to the catalog, we can see it link to it’s parent (which is the catalog).

In [13]:
item.get_parent()
Out[13]:
type "Catalog"
id "tutorial-catalog"
stac_version "1.0.0"
description "This catalog is a basic demonstration catalog utilizing a scene from SpaceNet 5."
links [] 1 items
You can also visualize the architecture of the STAC Catalog by using the describe() method. As a reminder, be careful when using it on large catalogs, as it will walk the entire tree of the STAC.

In [14]:
catalog.describe()
* <Catalog id=tutorial-catalog>
  * <Item id=local-image>
Add STAC Assets¶
We’ve created an item, but there aren’t any assets associated with it. Let’s create one. As always, take a look at the PySTAC API Documentation to see what components are needed to create an Asset.

In [15]:
# Add Asset and all its information to Item 
item.add_asset(
    key='image',
    asset=pystac.Asset(
        href=img_path,
        media_type=pystac.MediaType.GEOTIFF
    )
)
JSON Progress Check¶
Run to_dict() on the STAC Item we created. Notice the asset is now set:

In [16]:
print(json.dumps(item.to_dict(), indent=4))
{
    "type": "Feature",
    "stac_version": "1.0.0",
    "id": "local-image",
    "properties": {
        "datetime": "2023-10-18T03:10:18.923211Z"
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [
                    37.6616853489879,
                    55.73478197572927
                ],
                [
                    37.6616853489879,
                    55.73882710285011
                ],
                [
                    37.66573047610874,
                    55.73882710285011
                ],
                [
                    37.66573047610874,
                    55.73478197572927
                ],
                [
                    37.6616853489879,
                    55.73478197572927
                ]
            ]
        ]
    },
    "links": [
        {
            "rel": "root",
            "href": null,
            "type": "application/json"
        },
        {
            "rel": "parent",
            "href": null,
            "type": "application/json"
        }
    ],
    "assets": {
        "image": {
            "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/image.tif",
            "type": "image/tiff; application=geotiff"
        }
    },
    "bbox": [
        37.6616853489879,
        55.73478197572927,
        37.66573047610874,
        55.73882710285011
    ],
    "stac_extensions": []
}
Note that the link href properties are null. The empty href links are OK for now, as we’re working with the STAC in memory. Next, we will write the Catalog out and set those HREFs.

Save the Catalog¶
As the JSON above indicates, there are no HREFs set on these in-memory items. PySTAC uses the self link on STAC objects to track where the file lives. Because we haven’t set them, they evaluate to None:

In [17]:
print(catalog.get_self_href() is None)
print(item.get_self_href() is None)
True
True
Set the Catalog's HREFs¶
In order to set the HREFs, we can use normalize_hrefs. This method will create a normalized set of HREFs for each STAC object in the catalog, according to the recommendations from the best practices document on how to lay out a catalog.

In [18]:
catalog.normalize_hrefs(os.path.join(tmp_dir.name, "stac"))
Now that we’ve normalized to a root directory (the temporary directory), we see that the self links are set:

In [19]:
print("Catalog HREF: ", catalog.get_self_href())
print("Item HREF: ", item.get_self_href())
Catalog HREF:  /var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/catalog.json
Item HREF:  /var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/local-image/local-image.json
We can now call save on the catalog, which will recursively save all the STAC objects to their respective self HREFs.

Save requires a CatalogType to be set. You can review the PySTAC API Documentation to learn about each CatalogType.

Here, we will be creating a ‘self-contained catalog.' This type is one that is designed for portability. Users may want to download an online catalog from and be able to use it on their local computer, so all links need to be relative.

Save the Catalog: Self Contained¶
In [20]:
catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
Take a look at the temporary directory to see the catalog and item.

In [21]:
!ls {tmp_dir.name}/stac/*
/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/catalog.json

/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/local-image:
local-image.json
Now that our Catalog has been written out to file, we can open it up and read it directly. We should see the previously null hrefs populated with paths to the respective STAC component.

In [22]:
with open(catalog.self_href) as f:
    print(f.read())
{
  "type": "Catalog",
  "id": "tutorial-catalog",
  "stac_version": "1.0.0",
  "description": "This catalog is a basic demonstration catalog utilizing a scene from SpaceNet 5.",
  "links": [
    {
      "rel": "root",
      "href": "./catalog.json",
      "type": "application/json"
    },
    {
      "rel": "item",
      "href": "./local-image/local-image.json",
      "type": "application/json"
    }
  ]
}
In [23]:
with open(item.self_href) as f:
    print(f.read())
{
  "type": "Feature",
  "stac_version": "1.0.0",
  "id": "local-image",
  "properties": {
    "datetime": "2023-10-18T03:10:18.923211Z"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [
          37.6616853489879,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73478197572927
        ]
      ]
    ]
  },
  "links": [
    {
      "rel": "root",
      "href": "../catalog.json",
      "type": "application/json"
    },
    {
      "rel": "parent",
      "href": "../catalog.json",
      "type": "application/json"
    }
  ],
  "assets": {
    "image": {
      "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/image.tif",
      "type": "image/tiff; application=geotiff"
    }
  },
  "bbox": [
    37.6616853489879,
    55.73478197572927,
    37.66573047610874,
    55.73882710285011
  ],
  "stac_extensions": []
}
Save the Catalog: Absolute Published¶
As you can see, all links are saved with relative paths. That’s because we used catalog_type=CatalogType.SELF_CONTAINED. If we save an Absolute Published Catalog, we’ll see absolute paths.

An Absolute Published Catalog is a catalog that uses absolute links for everything, both in the links objects and in the asset hrefs.

Let's try saving the same catalog with the CatalogType as ABSOLUTE_PUBLISHED.

In [24]:
catalog.save(catalog_type=pystac.CatalogType.ABSOLUTE_PUBLISHED)
Now the links included in the STAC Item are all absolute:

In [25]:
with open(item.get_self_href()) as f:
    print(f.read())
{
  "type": "Feature",
  "stac_version": "1.0.0",
  "id": "local-image",
  "properties": {
    "datetime": "2023-10-18T03:10:18.923211Z"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [
          37.6616853489879,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73478197572927
        ]
      ]
    ]
  },
  "links": [
    {
      "rel": "root",
      "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/catalog.json",
      "type": "application/json"
    },
    {
      "rel": "parent",
      "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/catalog.json",
      "type": "application/json"
    },
    {
      "rel": "self",
      "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/stac/local-image/local-image.json",
      "type": "application/json"
    }
  ],
  "assets": {
    "image": {
      "href": "/var/folders/73/z5lbqv_s6l7fcfx464_pn8p80000gn/T/tmp17i4icyl/image.tif",
      "type": "image/tiff; application=geotiff"
    }
  },
  "bbox": [
    37.6616853489879,
    55.73478197572927,
    37.66573047610874,
    55.73882710285011
  ],
  "stac_extensions": []
}
Notice that the asset href is absolute in both cases. We can make the asset href relative to the STAC Item by using .make_all_asset_hrefs_relative():

In [26]:
catalog.make_all_asset_hrefs_relative()
catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
In [27]:
with open(item.get_self_href()) as f:
    print(f.read())
{
  "type": "Feature",
  "stac_version": "1.0.0",
  "id": "local-image",
  "properties": {
    "datetime": "2023-10-18T03:10:18.923211Z"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [
          37.6616853489879,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73882710285011
        ],
        [
          37.66573047610874,
          55.73478197572927
        ],
        [
          37.6616853489879,
          55.73478197572927
        ]
      ]
    ]
  },
  "links": [
    {
      "rel": "root",
      "href": "../catalog.json",
      "type": "application/json"
    },
    {
      "rel": "parent",
      "href": "../catalog.json",
      "type": "application/json"
    }
  ],
  "assets": {
    "image": {
      "href": "../../image.tif",
      "type": "image/tiff; application=geotiff"
    }
  },
  "bbox": [
    37.6616853489879,
    55.73478197572927,
    37.66573047610874,
    55.73882710285011
  ],
  "stac_extensions": []
}
There you have it: your very first STAC Catalog. In the following tutorial, you will learn how to add an Item with EO Extensions and a STAC Collection to this STAC Catalog.

Cleanup¶
Don't forget to clean up the temporary directory.

In [28]:
tmp_dir.cleanup()

