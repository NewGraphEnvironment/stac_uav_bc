from pystac import Collection, Extent, SpatialExtent, TemporalExtent
from datetime import datetime

# Define spatial extent (bounding box for BC)
spatial_extent = SpatialExtent([[-140, 48, -114, 60]])

# Define temporal extent using datetime objects
temporal_extent = TemporalExtent([[datetime(2020, 1, 1), datetime(2025, 1, 1)]])

# Create the extent object
extent = Extent(spatial=spatial_extent, temporal=temporal_extent)

# Create the STAC Collection
collection = Collection(
    id="uav-imagery-bc",
    description="A collection of UAV imagery from British Columbia",
    extent=extent,
    license="CC-BY-4.0",
    title="UAV Imagery from British Columbia"
)

# Save the collection JSON
collection.set_self_href("./bc-uav-collection.json")
collection.save()
