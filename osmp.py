"""Facilitates access to trail data provided by the City of Boulder.

Boulder's Open Space and Mountain Parks (OSMP) provides public access
to all sorts of data about the trail network, and even provides some
data to trails in adjacent jurisdictions. To my knowledge, no such
high-quality data exists elsewhere. 

This data is accessible via an arcgis REST server. Until recently,
the entire arcgis database structure was browseable via HTML.
This is no longer the case, so I needed to develop an interface
to continue to access and explore this data. The purpose of the osmp
module is to provide a more transparent, easy-to-navigate face to
Boulder's OSMP data.
"""

import arcgis


SERVER_URL = 'https://maps.bouldercolorado.gov/arcgis2/rest/services/osmp/'


class OsmpFeatureLayerCollection(arcgis.features.FeatureLayerCollection):
  """Base class representing an entire OSMP MapServer.

  Items of interest are DogRegs, Trails, TrailsNEW,
  TrailheadsAccessPoints, AllWildlifeClosures, UndesignatedTrails, ... 

  Construction of an OsmpFeatureLayerCollection opens a connection to
  the indicated OSMP MapServer.

  TODO: 
  - Build out subclasses: Items of interest above.
  """

  def __init__(self, server_name):
    """Creates an OsmpFeatureLayerCollection from a MapServer url.

    Args:
      server_name: A string representing the directory of the MapServer
                   within OSMP's directory structure.
    """
    server_url = SERVER_URL + server_name + '/MapServer/'
    super(OsmpFeatureLayerCollection, self).__init__(server_url)

  def _get_layer_by_value(self, property_name, value):
    try:
      return next(layer for layer in self.layers
                  if layer.properties[property_name] == value)
    except StopIteration:
      return None

  def get_layer_by_id(self, layer_id):
    return self._get_layer_by_value('id', layer_id)

  def get_layer_by_name(self, layer_name):
    return self._get_layer_by_value('name', layer_name)

  def get_feature(self, ftr_id, layer_id=0, id_field_name='GlobalID',
                  fields='*'):
    """TODO: Catch correct exception, including multiple records returned."""
    layer = self.get_layer_by_id(layer_id)
    query_where = id_field_name + "='" + ftr_id + "'"
    try:
      query_result = layer.query(where=query_where,
                                 out_fields=fields,
                                 out_sr='4326')
    except RuntimeError:
      return None

    if len(query_result.features) > 0:
      return query_result.features[0]


class Trails(OsmpFeatureLayerCollection):
  """Provides access to OSMP's Trails MapServer."""

  def __init__(self):
    super(Trails, self).__init__('Trails')


class TrailsNew(OsmpFeatureLayerCollection):
  """Provides access to OSMP's TrailsNEW MapServer."""

  def __init__(self):
    super(TrailsNew, self).__init__('TrailsNEW')


class Junctions(OsmpFeatureLayerCollection):
  """Provides access to OSMP's TrailJunctions MapServer."""

  def __init__(self):
    super(Junctions, self).__init__('TrailJunctions')
 

class DogRegs(OsmpFeatureLayerCollection):
  """Provides access to OSMP's DogRegs MapServer."""

  def __init__(self):
    super(DogRegs, self).__init__('DogRegs')


class OsmpFeature(arcgis.features.Feature):
  """Base class representing a feature from OSMP's arcgis server.

  Items of interest are access points, junctions, parking areas, 
  trail segments, trails(?), ...

  Construction of an OsmpFeature reads in the feature geometry and
  attributes, and uses them to create itself.

  TODO: 
  - Build out subclasses: Trails (OSMP segment, boco segment, other),
    intersection, access, ... basically all types I've defined
    in boulderhikes.models.
  """

  def __init__(self, feature):
    """Creates an OsmpFeature from a typical arcgis Feature.

    Args:
      feature: An arcgis.features.Feature object.
    """

    super(OsmpFeature, self).__init__(geometry=feature.geometry,
                                      attributes=feature.attributes)
    #self.id = db_id
    #self.id_field_name = id_field_name

    # Memoize for later use.
    self._latlon_coords = None
    self._name = None

  @property
  def is_line(self):
    return self.geometry_type == 'Polyline'

  @property
  def is_point(self):
    return self.geometry_type == 'Point'

  @property
  def latlon_coords(self):
    if self._latlon_coords is None:
      if self.is_line:
        self._latlon_coords = self.geometry['paths'][0]
      elif self.is_point:
        self._latlon_coords = [self.geometry['y'], self.geometry['x']]

    return self._latlon_coords

  @property
  def name(self):
    """A basic implementation that expects to be overriden."""
    return self._name


class Trail(OsmpFeature):
  """Represents a trail segment in OSMP's arcgis database.

  Construction of a Trail results in a query of relevant databases
  to locate the feature of interest using the id.
  """

  def __init__(self, db_id):
    """
    Args:
      db_id: A string representing one of several trail id options.
        - 'SEGMENTID': A string with format 'ddd-ddd-ddd', where d is
                       an integer. The three sets of three digits
                       represent the TRAILNUMBER of the named trail,
                       the JUNCTION_ID of the starting Trail Junction,
                       and the JUNCTION_ID Of the ending Trail Junction,
                       respectively.
        - 'GlobalID': A 128-bit string that uniquely and unchangingly
                      identifies the Trail object in the database.
                      Typically has format:
                      '{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}'
    """
    self.id = db_id

    # Check if db_id corresponds to OSMP trail.
    # If not, assume it belongs to the Other Area Trails layer. Then
    # initialize the correct MapServer as a FeatureLayerCollection
    # and get the feature corresponding to self.id.
    #
    # TODO: Make OsmpFeatureLayerCollection smarter. What? 
    if self.is_osmp_trail:
      self.id_field_name = 'SEGMENTID'
      feature = Trails().get_feature(self.id,
                                     layer_id=4,
                                     id_field_name=self.id_field_name)
    else:
      #self.id_field_name = 'OBJECTID'
      self.id_field_name = 'GlobalID'
      #self.id_field_name = 'BATTrailID'
      feature = TrailsNew().get_feature(self.id,
                                        layer_id=7,
                                        id_field_name=self.id_field_name)

    super(Trail, self).__init__(feature)

  @property
  def is_osmp_trail(self):
    pattern = re.compile('^[0-9]{3}-[0-9]{3}-[0-9]{3}$')

    return pattern.match(self.id) is not None

  @property
  def name(self):
    if self._name is None:
      self._name = self.get_value('TRAILNAME')
    
    return self._name


class Access(OsmpFeature):

  def __init__(self, db_id):
    self.id = db_id
    self.id_field_name = 'ACCESSID'
    feature = OsmpFeatureLayerCollection(
        'TrailheadsAccessPoints').get_feature(self.id,
                                  layer_id=0,
                                  id_field_name=self.id_field_name)
    super(Access, self).__init__(feature)


class Junction(OsmpFeature):

  def __init__(self, db_id):
    self.id = db_id
    self.id_field_name = 'JUNCTIONID'
    feature = Trails().get_feature(self.id,
                                   layer_id=1,
                                   id_field_name=self.id_field_name)
    super(Junction, self).__init__(feature)
