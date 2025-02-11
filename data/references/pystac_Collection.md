

 
class Collection(pystac.catalog.Catalog, pystac.asset.Assets)
   	Collection(id: 'str', description: 'str', extent: 'Extent', title: 'str | None' = None, stac_extensions: 'list[str] | None' = None, href: 'str | None' = None, extra_fields: 'dict[str, Any] | None' = None, catalog_type: 'CatalogType | None' = None, license: 'str' = 'other', keywords: 'list[str] | None' = None, providers: 'list[Provider] | None' = None, summaries: 'Summaries | None' = None, assets: 'dict[str, Asset] | None' = None, strategy: 'HrefLayoutStrategy | None' = None)
 
A Collection extends the Catalog spec with additional metadata that helps
enable discovery.
 
Args:
    id : Identifier for the collection. Must be unique within the STAC.
    description : Detailed multi-line description to fully explain the
        collection. `CommonMark 0.29 syntax <https://commonmark.org/>`_ MAY
        be used for rich text representation.
    extent : Spatial and temporal extents that describe the bounds of
        all items contained within this Collection.
    title : Optional short descriptive one-line title for the
        collection.
    stac_extensions : Optional list of extensions the Collection
        implements.
    href : Optional HREF for this collection, which be set as the
        collection's self link's HREF.
    catalog_type : Optional catalog type for this catalog. Must
        be one of the values in :class`~pystac.CatalogType`.
    license :  Collection's license(s) as a
        `SPDX License identifier <https://spdx.org/licenses/>`_,
        or `other`. If collection includes data with multiple
        different licenses, use `other` and add a link for
        each. The licenses `various` and `proprietary` are deprecated.
        Defaults to 'other'.
    keywords : Optional list of keywords describing the collection.
    providers : Optional list of providers of this Collection.
    summaries : An optional map of property summaries,
        either a set of values or statistics such as a range.
    extra_fields : Extra fields that are part of the top-level
        JSON properties of the Collection.
    assets : A dictionary mapping string keys to :class:`~pystac.Asset` objects. All
        :class:`~pystac.Asset` values in the dictionary will have their
        :attr:`~pystac.Asset.owner` attribute set to the created Collection.
    strategy : The layout strategy to use for setting the
        HREFs of the catalog child objections and items.
        If not provided, it will default to strategy of the parent and fallback to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`.
 
 	
Method resolution order:
Collection
pystac.catalog.Catalog
pystac.stac_object.STACObject
abc.ABC
pystac.asset.Assets
typing.Protocol
typing.Generic
builtins.object
Methods defined here:
__init__(self, id: 'str', description: 'str', extent: 'Extent', title: 'str | None' = None, stac_extensions: 'list[str] | None' = None, href: 'str | None' = None, extra_fields: 'dict[str, Any] | None' = None, catalog_type: 'CatalogType | None' = None, license: 'str' = 'other', keywords: 'list[str] | None' = None, providers: 'list[Provider] | None' = None, summaries: 'Summaries | None' = None, assets: 'dict[str, Asset] | None' = None, strategy: 'HrefLayoutStrategy | None' = None)
Initialize self.  See help(type(self)) for accurate signature.
__repr__(self) -> 'str'
Return repr(self).
__subclasshook__ = _proto_hook(other) from typing.Protocol.__init_subclass__.
# Set (or override) the protocol subclass hook.
add_item(self, item: 'Item', title: 'str | None' = None, strategy: 'HrefLayoutStrategy | None' = None, set_parent: 'bool' = True) -> 'Link'
Adds a link to an :class:`~pystac.Item`.
 
This method will set the item's parent to this object and potentially
override its self_link (unless ``set_parent`` is False)
 
It will always set its root to this Catalog's root.
 
Args:
    item : The item to add.
    title : Optional title to give to the :class:`~pystac.Link`
    strategy : The layout strategy to use for setting the
        self href of the item. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`.
    set_parent : Whether to set the parent on the item as well.
        Defaults to True.
 
Returns:
    Link: The link created for the item
clone(self) -> 'Collection'
Clones this object.
 
pystac.Collection
help(Collection)

Cloning an object will make a copy of all properties and links of the object;
however, it will not make copies of the targets of links (i.e. it is not a
deep copy). To copy a STACObject fully, with all linked elements also copied,
use :func:`~pystac.STACObject.full_copy`.
 
Returns:
    STACObject: The clone of this object.
full_copy(self, root: 'Catalog | None' = None, parent: 'Catalog | None' = None) -> 'Collection'
Create a full copy of this STAC object and any STAC objects linked to by
this object.
 
Args:
    root : Optional root to set as the root of the copied object,
        and any other copies that are contained by this object.
    parent : Optional parent to set as the parent of the copy
        of this object.
 
Returns:
    STACObject: A full copy of this object, as well as any objects this object
        links to.
get_item(self, id: 'str', recursive: 'bool' = False) -> 'Item | None'
Returns an item with a given ID.
 
Args:
    id : The ID of the item to find.
    recursive : If True, search this collection and all children for the
        item; otherwise, only search the items of this collection. Defaults
        to False.
 
Return:
    Item or None: The item with the given ID, or None if not found.
to_dict(self, include_self_link: 'bool' = True, transform_hrefs: 'bool' = True) -> 'dict[str, Any]'
Returns this object as a dictionary.
 
Args:
    include_self_link : If True, the dict will contain a self link
        to this object. If False, the self link will be omitted.
    transform_hrefs: If True, transform the HREF of hierarchical links
        based on the type of catalog this object belongs to (if any).
        I.e. if this object belongs to a root catalog that is
        RELATIVE_PUBLISHED or SELF_CONTAINED,
        hierarchical link HREFs will be transformed to be relative to the
        catalog root.
 
    dict: A serialization of the object.
update_extent_from_items(self) -> 'None'
Update datetime and bbox based on all items to a single bbox and time window.
Class methods defined here:
from_dict(d: 'dict[str, Any]', href: 'str | None' = None, root: 'Catalog | None' = None, migrate: 'bool' = False, preserve_dict: 'bool' = True) -> 'C'
Parses this STACObject from the passed in dictionary.
 
Args:
    d : The dict to parse.
    href : Optional href that is the file location of the object being
        parsed.
    root : Optional root catalog for this object.
        If provided, the root of the returned STACObject will be set
        to this parameter.
    migrate: Use True if this dict represents JSON from an older STAC object,
        so that migrations are run against it.
    preserve_dict: If False, the dict parameter ``d`` may be modified
        during this method call. Otherwise the dict is not mutated.
        Defaults to True, which results results in a deepcopy of the
        parameter. Set to False when possible to avoid the performance
        hit of a deepcopy.
 
Returns:
    STACObject: The STACObject parsed from this dict.
matches_object_type(d: 'dict[str, Any]') -> 'bool'
Returns a boolean indicating whether the given dictionary represents a valid
instance of this :class:`~pystac.STACObject` sub-class.
 
Args:
    d : A dictionary to identify
Readonly properties defined here:
ext
Accessor for extension classes on this collection
 
Example::
 
    print(collection.ext.xarray)
Data descriptors defined here:
item_assets
Accessor for `item_assets
<https://github.com/radiantearth/stac-spec/blob/v1.1.0/collection-spec/collection-spec.md#item_assets>`__
on this collection.
 
Example::
 
.. code-block:: python
 
   >>> print(collection.item_assets)
   {'thumbnail': <pystac.item_assets.ItemAssetDefinition at 0x72aea0420750>,
    'metadata': <pystac.item_assets.ItemAssetDefinition at 0x72aea017dc90>,
    'B5': <pystac.item_assets.ItemAssetDefinition at 0x72aea017efd0>,
    'B6': <pystac.item_assets.ItemAssetDefinition at 0x72aea016d5d0>,
    'B7': <pystac.item_assets.ItemAssetDefinition at 0x72aea016e050>,
    'B8': <pystac.item_assets.ItemAssetDefinition at 0x72aea016da90>}
   >>> collection.item_assets["thumbnail"].title
   'Thumbnail'
 
Set attributes on :class:`~pystac.ItemAssetDefinition` objects
 
.. code-block:: python
 
   >>> collection.item_assets["thumbnail"].title = "New Title"
 
Add to the ``item_assets`` dict:
 
.. code-block:: python
 
   >>> collection.item_assets["B4"] = {
       'type': 'image/tiff; application=geotiff; profile=cloud-optimized',
       'eo:bands': [{'name': 'B4', 'common_name': 'red'}]
   }
   >>> collection.item_assets["B4"].owner == collection
   True
Data and other attributes defined here:
DEFAULT_FILE_NAME = 'collection.json'
STAC_OBJECT_TYPE = 'Collection'
__abstractmethods__ = frozenset()
__annotations__ = {'description': 'str', 'extent': 'Extent', 'extra_fields': 'dict[str, Any]', 'id': 'str', 'keywords': 'list[str] | None', 'links': 'list[Link]', 'providers': 'list[Provider] | None', 'stac_extensions': 'list[str]', 'summaries': 'Summaries', 'title': 'str | None'}
__parameters__ = ()
Methods inherited from pystac.catalog.Catalog:
add_child(self, child: 'Catalog | Collection', title: 'str | None' = None, strategy: 'HrefLayoutStrategy | None' = None, set_parent: 'bool' = True) -> 'Link'
Adds a link to a child :class:`~pystac.Catalog` or
:class:`~pystac.Collection`.
 
This method will set the child's parent to this object and potentially
override its self_link (unless ``set_parent`` is False).
 
It will always set its root to this Catalog's root.
 
Args:
    child : The child to add.
    title : Optional title to give to the :class:`~pystac.Link`
    strategy : The layout strategy to use for setting the
        self href of the child. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`.
    set_parent : Whether to set the parent on the child as well.
        Defaults to True.
 
Returns:
    Link: The link created for the child
add_children(self, children: 'Iterable[Catalog | Collection]', strategy: 'HrefLayoutStrategy | None' = None) -> 'list[Link]'
Adds links to multiple :class:`~pystac.Catalog` or `~pystac.Collection`
objects. This method will set each child's parent to this object, and their
root to this Catalog's root.
 
Args:
    children : The children to add.
    strategy : The layout strategy to use for setting the
        self href of the children. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`.
 
Returns:
    List[Link]: An array of links created for the children
add_items(self, items: 'Iterable[Item]', strategy: 'HrefLayoutStrategy | None' = None) -> 'list[Link]'
Adds links to multiple :class:`Items <pystac.Item>`.
 
This method will set each item's parent to this object, and their root to
this Catalog's root.
 
Args:
    items : The items to add.
    strategy : The layout strategy to use for setting the
        self href of the items. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`.
 
Returns:
    List[Link]: A list of links created for the item
clear_children(self) -> 'None'
Removes all children from this catalog.
 
Return:
    Catalog: Returns ``self``
clear_items(self) -> 'None'
Removes all items from this catalog.
 
Return:
    Catalog: Returns ``self``
describe(self, include_hrefs: 'bool' = False, _indent: 'int' = 0) -> 'None'
Prints out information about this Catalog and all contained
STACObjects.
 
Args:
    include_hrefs (bool) - If True, print out each object's self link
        HREF along with the object ID.
fully_resolve(self) -> 'None'
Resolves every link in this catalog.
 
Useful if, e.g., you'd like to read a catalog from a filesystem, upgrade
every object in the catalog to the latest STAC version, and save it back
to the filesystem. By default, :py:meth:`~pystac.Catalog.save` skips
unresolved links.
generate_subcatalogs(self, template: 'str', defaults: 'dict[str, Any] | None' = None, parent_ids: 'list[str] | None' = None) -> 'list[Catalog]'
Walks through the catalog and generates subcatalogs
for items based on the template string.
 
See :class:`~pystac.layout.LayoutTemplate`
for details on the construction of template strings. This template string
will be applied to the items, and subcatalogs will be created that separate
and organize the items based on template values.
 
Args:
    template :   A template string that
        can be consumed by a :class:`~pystac.layout.LayoutTemplate`
    defaults :  Default values for the template variables
        that will be used if the property cannot be found on
        the item.
    parent_ids : Optional list of the parent catalogs'
        identifiers. If the bottom-most subcatalogs already match the
        template, no subcatalog is added.
 
Returns:
    list[Catalog]: List of new catalogs created
get_all_collections(self) -> 'Iterable[Collection]'
Get all collections from this catalog and all subcatalogs. Will traverse
any subcatalogs recursively.
get_all_items(self) -> 'Iterator[Item]'
DEPRECATED.
 
.. deprecated:: 1.8
    Use ``pystac.Catalog.get_items(recursive=True)`` instead.
 
Get all items from this catalog and all subcatalogs. Will traverse
any subcatalogs recursively.
 
Returns:
    Generator[Item]: All items that belong to this catalog, and all
        catalogs or collections connected to this catalog through
        child links.
get_child(self, id: 'str', recursive: 'bool' = False, sort_links_by_id: 'bool' = True) -> 'Catalog | Collection | None'
Gets the child of this catalog with the given ID, if it exists.
 
Args:
    id : The ID of the child to find.
    recursive : If True, search this catalog and all children for the
        item; otherwise, only search the children of this catalog. Defaults
        to False.
    sort_links_by_id : If True, links containing the ID will be checked
        first. If links do not contain the ID then setting this to False
        will improve performance. Defaults to True.
 
Return:
    Catalog or Collection or None: The child with the given ID,
    or None if not found.
get_child_links(self) -> 'list[Link]'
Return all child links of this catalog.
 
Return:
    List[Link]: List of links of this catalog with ``rel == 'child'``
get_children(self) -> 'Iterable[Catalog | Collection]'
Return all children of this catalog.
 
Return:
    Iterable[Catalog or Collection]: Iterable of children who's parent
    is this catalog.
get_collections(self) -> 'Iterable[Collection]'
Return all children of this catalog that are :class:`~pystac.Collection`
instances.
get_item_links(self) -> 'list[Link]'
Return all item links of this catalog.
 
Return:
    List[Link]: List of links of this catalog with ``rel == 'item'``
get_items(self, *ids: 'str', recursive: 'bool' = False) -> 'Iterator[Item]'
Return all items or specific items of this catalog.
 
Args:
    *ids : The IDs of the items to include.
    recursive : If True, search this catalog and all children for the
        item; otherwise, only search the items of this catalog. Defaults
        to False.
 
Return:
    Iterator[Item]: Generator of items whose parent is this catalog, and
        (if recursive) all catalogs or collections connected to this catalog
        through child links.
is_relative(self) -> 'bool'
make_all_asset_hrefs_absolute(self) -> 'None'
Recursively makes all the HREFs of assets in this catalog absolute
make_all_asset_hrefs_relative(self) -> 'None'
Recursively makes all the HREFs of assets in this catalog relative
map_assets(self, asset_mapper: 'Callable[[str, Asset], Asset | tuple[str, Asset] | dict[str, Asset]]') -> 'Catalog'
Creates a copy of a catalog, with each Asset for each Item passed
through the asset_mapper function.
 
Args:
    asset_mapper : A function that takes in an key and an Asset, and
        returns either an Asset, a (key, Asset), or a dictionary of Assets with
        unique keys. The Asset that is passed into the item_mapper is a copy,
        so the method can mutate it safely.
 
Returns:
    Catalog: A full copy of this catalog, with assets manipulated according
    to the asset_mapper function.
map_items(self, item_mapper: 'Callable[[Item], Item | list[Item]]') -> 'Catalog'
Creates a copy of a catalog, with each item passed through the
item_mapper function.
 
Args:
    item_mapper :   A function that takes in an item, and returns
        either an item or list of items. The item that is passed into the
        item_mapper is a copy, so the method can mutate it safely.
 
Returns:
    Catalog: A full copy of this catalog, with items manipulated according
    to the item_mapper function.
normalize_and_save(self, root_href: 'str', catalog_type: 'CatalogType | None' = None, strategy: 'HrefLayoutStrategy | None' = None, stac_io: 'pystac.StacIO | None' = None, skip_unresolved: 'bool' = False) -> 'None'
Normalizes link HREFs to the given root_href, and saves the catalog.
 
This is a convenience method that simply calls :func:`Catalog.normalize_hrefs
<pystac.Catalog.normalize_hrefs>` and :func:`Catalog.save <pystac.Catalog.save>`
in sequence.
 
Args:
    root_href : The absolute HREF that all links will be normalized
        against.
    catalog_type : The catalog type that dictates the structure of
        the catalog to save. Use a member of :class:`~pystac.CatalogType`.
        Defaults to the root catalog.catalog_type or the current catalog
        catalog_type if there is no root catalog.
    strategy : The layout strategy to use in setting the
        HREFS for this catalog. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`
    stac_io : Optional instance of :class:`~pystac.StacIO` to use. If not
        provided, will use the instance set while reading in the catalog,
        or the default instance if this is not available.
    skip_unresolved : Skip unresolved links when normalizing the tree.
        Defaults to False. Because unresolved links are not saved, this
        argument can be used to normalize and save only newly-added
        objects.
normalize_hrefs(self, root_href: 'str', strategy: 'HrefLayoutStrategy | None' = None, skip_unresolved: 'bool' = False) -> 'None'
Normalize HREFs will regenerate all link HREFs based on
an absolute root_href and the canonical catalog layout as specified
in the STAC specification's best practices.
 
This method mutates the entire catalog tree, unless ``skip_unresolved``
is True, in which case only resolved links are modified. This is useful
in the case when you have loaded a large catalog and you've added a few
items/children, and you only want to update those newly-added objects,
not the whole tree.
 
Args:
    root_href : The absolute HREF that all links will be normalized against.
    strategy : The layout strategy to use in setting the HREFS
        for this catalog. If not provided, defaults to
        the layout strategy of the parent or root and falls back to
        :class:`~pystac.layout.BestPracticesLayoutStrategy`
    skip_unresolved : Skip unresolved links when normalizing the tree.
        Defaults to False.
 
See:
    :stac-spec:`STAC best practices document <best-practices.md#catalog-layout>`
    for the canonical layout of a STAC.
remove_child(self, child_id: 'str') -> 'None'
Removes an child from this catalog.
 
Args:
    child_id : The ID of the child to remove.
remove_item(self, item_id: 'str') -> 'None'
Removes an item from this catalog.
 
Args:
    item_id : The ID of the item to remove.
save(self, catalog_type: 'CatalogType | None' = None, dest_href: 'str | None' = None, stac_io: 'pystac.StacIO | None' = None) -> 'None'
Save this catalog and all it's children/item to files determined by the
object's self link HREF or a specified path.
 
Args:
    catalog_type : The catalog type that dictates the structure of
        the catalog to save. Use a member of :class:`~pystac.CatalogType`.
        If not supplied, the catalog_type of this catalog will be used.
        If that attribute is not set, an exception will be raised.
    dest_href : The location where the catalog is to be saved.
        If not supplied, the catalog's self link HREF is used to determine
        the location of the catalog file and children's files.
    stac_io : Optional instance of :class:`~pystac.StacIO` to use. If not
        provided, will use the instance set while reading in the catalog,
        or the default instance if this is not available.
Note:
    If the catalog type is ``CatalogType.ABSOLUTE_PUBLISHED``,
    all self links will be included, and hierarchical links be absolute URLs.
    If the catalog type is ``CatalogType.RELATIVE_PUBLISHED``, this catalog's
    self link will be included, but no child catalog will have self links, and
    hierarchical links will be relative URLs
    If the catalog  type is ``CatalogType.SELF_CONTAINED``, no self links will
    be included and hierarchical links will be relative URLs.
set_root(self, root: 'Catalog | None') -> 'None'
Sets the root :class:`~pystac.Catalog` or :class:`~pystac.Collection`
for this object.
 
Args:
    root : The root
        object to set. Passing in None will clear the root.
validate_all(self, max_items: 'int | None' = None, recursive: 'bool' = True) -> 'int'
Validates each catalog, collection, item contained within this catalog.
 
Walks through the children and items of the catalog and validates each
stac object.
 
Args:
    max_items : The maximum number of STAC items to validate. Default
        is None which means, validate them all.
    recursive : Whether to validate catalog, collections, and items contained
        within child objects.
 
Returns:
    int : Number of STAC items validated.
 
Raises:
    STACValidationError: Raises this error on any item that is invalid.
        Will raise on the first invalid stac object encountered.
walk(self) -> 'Iterable[tuple[Catalog, Iterable[Catalog], Iterable[Item]]]'
Walks through children and items of catalogs.
 
For each catalog in the STAC's tree rooted at this catalog (including this
catalog itself), it yields a 3-tuple (root, subcatalogs, items). The root in
that 3-tuple refers to the current catalog being walked, the subcatalogs are any
catalogs or collections for which the root is a parent, and items represents
any items that have the root as a parent.
 
This has similar functionality to Python's :func:`os.walk`.
 
Returns:
   Generator[(Catalog, Generator[Catalog], Generator[Item])]: A generator that
   yields a 3-tuple (parent_catalog, children, items).
Class methods inherited from pystac.catalog.Catalog:
from_file(href: 'HREF', stac_io: 'pystac.StacIO | None' = None) -> 'C'
Reads a STACObject implementation from a file.
 
Args:
    href : The HREF to read the object from.
    stac_io: Optional instance of StacIO to use. If not provided, will use the
        default instance.
 
Returns:
    The specific STACObject implementation class that is represented
    by the JSON read from the file located at HREF.
Methods inherited from pystac.stac_object.STACObject:
add_link(self, link: 'Link') -> 'None'
Add a link to this object's set of links.
 
Args:
     link : The link to add.
add_links(self, links: 'list[Link]') -> 'None'
Add links to this object's set of links.
 
Args:
     links : The links to add.
clear_links(self, rel: 'str | pystac.RelType | None' = None) -> 'None'
Clears all :class:`~pystac.Link` instances associated with this object.
 
Args:
    rel : If set, only clear links that match this relationship.
get_links(self, rel: 'str | pystac.RelType | None' = None, media_type: 'OptionalMediaType | Iterable[OptionalMediaType]' = None) -> 'list[Link]'
Gets the :class:`~pystac.Link` instances associated with this object.
 
Args:
    rel : If set, filter links such that only those
        matching this relationship are returned.
    media_type: If set, filter the links such that only
        those matching media_type are returned. media_type can
        be a single value or a list of values.
 
Returns:
    List[:class:`~pystac.Link`]: A list of links that match ``rel`` and/
        or ``media_type`` if set, or else all links associated with this
        object.
get_parent(self) -> 'Catalog | None'
Get the :class:`~pystac.Catalog` or :class:`~pystac.Collection` to
the parent for this object. The root is represented by a
:class:`~pystac.Link` with ``rel == 'parent'``.
 
Returns:
    Catalog, Collection, or None:
        The parent object for this object,
        or ``None`` if no root link is set.
get_root(self) -> 'Catalog | None'
Get the :class:`~pystac.Catalog` or :class:`~pystac.Collection` to
the root for this object. The root is represented by a
:class:`~pystac.Link` with ``rel == 'root'``.
 
Returns:
    Catalog, Collection, or None:
        The root object for this object, or ``None`` if no root link is set.
get_root_link(self) -> 'Link | None'
Get the :class:`~pystac.Link` representing
the root for this object.
 
Returns:
    :class:`~pystac.Link` or None: The root link for this object,
    or ``None`` if no root link is set.
get_self_href(self) -> 'str | None'
Gets the absolute HREF that is represented by the ``rel == 'self'``
:class:`~pystac.Link`.
 
Returns:
    str or None: The absolute HREF of this object, or ``None`` if
    there is no self link defined.
 
Note:
    A self link can exist for objects, even if the link is not read or
    written to the JSON-serialized version of the object. Any object
    read from :func:`STACObject.from_file <pystac.STACObject.from_file>` will
    have the HREF the file was read from set as it's self HREF. All self
    links have absolute (as opposed to relative) HREFs.
get_single_link(self, rel: 'str | pystac.RelType | None' = None, media_type: 'OptionalMediaType | Iterable[OptionalMediaType]' = None) -> 'Link | None'
Get a single :class:`~pystac.Link` instance associated with this
object.
 
Args:
    rel : If set, filter links such that only those
        matching this relationship are returned.
    media_type: If set, filter the links such that only
        those matching media_type are returned. media_type can
        be a single value or a list of values.
 
Returns:
    :class:`~pystac.Link` | None: First link that matches ``rel``
        and/or ``media_type``, or else the first link associated with
        this object.
get_stac_objects(self, rel: 'str | pystac.RelType', typ: 'type[STACObject] | None' = None, modify_links: 'Callable[[list[Link]], list[Link]] | None' = None) -> 'Iterable[STACObject]'
Gets the :class:`STACObject` instances that are linked to
by links with their ``rel`` property matching the passed in argument.
 
Args:
    rel : The relation to match each :class:`~pystac.Link`'s
        ``rel`` property against.
    typ : If not ``None``, objects will only be yielded if they are instances of
        ``typ``.
    modify_links : A function that modifies the list of links before they are
        iterated over. For instance, this option can be used to sort the list
        so that links matching a particular pattern are earlier in the iterator.
 
Returns:
    Iterable[STACObject]: A possibly empty iterable of STACObjects that are
        connected to this object through links with the given ``rel`` and are of
        type ``typ`` (if given).
remove_hierarchical_links(self, add_canonical: 'bool' = False) -> 'list[Link]'
Removes all hierarchical links from this object.
 
See :py:const:`pystac.link.HIERARCHICAL_LINKS` for a list of all
hierarchical links. If the object has a ``self`` href and
``add_canonical`` is True, a link with ``rel="canonical"`` is added.
 
Args:
    add_canonical : If true, and this item has a ``self`` href, that
        href is used to build a ``canonical`` link.
 
Returns:
    List[Link]: All removed links
remove_links(self, rel: 'str | pystac.RelType') -> 'None'
Remove links to this object's set of links that match the given ``rel``.
 
Args:
     rel : The :class:`~pystac.Link` ``rel`` to match on.
resolve_links(self) -> 'None'
Ensure all STACObjects linked to by this STACObject are
resolved. This is important for operations such as changing
HREFs.
 
This method mutates the entire catalog tree.
save_object(self, include_self_link: 'bool' = True, dest_href: 'str | None' = None, stac_io: 'pystac.StacIO | None' = None) -> 'None'
Saves this :class:`STACObject` to it's 'self' HREF.
 
Args:
    include_self_link : If this is true, include the 'self' link with
        this object. Otherwise, leave out the self link.
    dest_href : Optional HREF to save the file to. If None, the object
        will be saved to the object's self href.
    stac_io: Optional instance of StacIO to use. If not provided, will use the
        instance set on the object's root if available, otherwise will use the
        default instance.
 
 
Raises:
    STACError: If no self href is set, this error will be raised.
 
Note:
    When to include a self link is described in the :stac-spec:`Use of Links
    section of the STAC best practices document
    <best-practices.md#use-of-links>`
set_parent(self, parent: 'Catalog | None') -> 'None'
Sets the parent :class:`~pystac.Catalog` or :class:`~pystac.Collection`
for this object.
 
Args:
    parent : The parent
        object to set. Passing in None will clear the parent.
set_self_href(self, href: 'str | None') -> 'None'
Sets the absolute HREF that is represented by the ``rel == 'self'``
:class:`~pystac.Link`.
 
Args:
    href : The absolute HREF of this object. If the given HREF
        is not absolute, it will be transformed to an absolute
        HREF based on the current working directory. If this is None
        the call will clear the self HREF link.
target_in_hierarchy(self, target: 'str | STACObject') -> 'bool'
Determine if target is somewhere in the hierarchical link tree of
a STACObject.
 
Args:
    target: A string or STACObject to search for
 
Returns:
    bool: Returns True if the target was found in the hierarchical link tree
        for the current STACObject
validate(self, validator: 'pystac.validation.stac_validator.STACValidator | None' = None) -> 'list[Any]'
Validate this STACObject.
 
Returns a list of validation results, which depends on the validation
implementation. For JSON Schema validation (default validator), this
will be a list of schema URIs that were used during validation.
 
Args:
    validator : A custom validator to use for validation of the object.
        If omitted, the default validator from
        :class:`~pystac.validation.RegisteredValidator`
        will be used instead.
Raises:
    STACValidationError
Readonly properties inherited from pystac.stac_object.STACObject:
self_href
Gets the absolute HREF that is represented by the ``rel == 'self'``
:class:`~pystac.Link`.
 
Raises:
    ValueError: If the self_href is not set, this method will throw
        a ValueError. Use get_self_href if there may not be an href set.
Data descriptors inherited from pystac.stac_object.STACObject:
__dict__
dictionary for instance variables
__weakref__
list of weak references to the object
Methods inherited from pystac.asset.Assets:
add_asset(self, key: 'str', asset: 'Asset') -> 'None'
Adds an Asset to this object.
 
Args:
    key : The unique key of this asset.
    asset : The Asset to add.
delete_asset(self, key: 'str') -> 'None'
Deletes the asset at the given key, and removes the asset's data
file from the local filesystem.
 
It is an error to attempt to delete an asset's file if it is on a
remote filesystem.
 
To delete the asset without removing the file, use `del item.assets["key"]`.
 
Args:
    key: The unique key of this asset.
get_assets(self, media_type: 'str | MediaType | None' = None, role: 'str | None' = None) -> 'dict[str, Asset]'
Get this object's assets.
 
Args:
    media_type: If set, filter the assets such that only those with a
        matching ``media_type`` are returned.
    role: If set, filter the assets such that only those with a matching
        ``role`` are returned.
 
Returns:
    Dict[str, Asset]: A dictionary of assets that match ``media_type``
        and/or ``role`` if set or else all of this object's assets.
make_asset_hrefs_absolute(self) -> 'Assets'
Modify each asset's HREF to be absolute.
 
Any asset HREFs that are relative will be modified to absolute based on this
item's self HREF.
 
Returns:
    Assets: self
make_asset_hrefs_relative(self) -> 'Assets'
Modify each asset's HREF to be relative to this object's self HREF.
 
Returns:
    Item: self
Class methods inherited from typing.Protocol:
__init_subclass__(*args, **kwargs)
This method is called when a class is subclassed.
 
The default implementation does nothing. It may be
overridden to extend subclasses.
Class methods inherited from typing.Generic:
__class_getitem__(params)
Parameterizes a generic class.
 
At least, parameterizing a generic class is the *main* thing this method
does. For example, for some generic class `Foo`, this is called when we
do `Foo[int]` - there, with `cls=Foo` and `params=int`.
 
However, note that this method is also called when defining generic
classes in the first place with `class Foo(Generic[T]): ...`.