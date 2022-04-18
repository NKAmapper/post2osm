# post2osm
Generates OSM files for post offices, parcel lockers and post boxes of Posten Norge.

### Usage

<code>python3 post2osm.py</code>

* This script will produce OSM files for post offices, parcel lockers and post boxes from Posten api.
* No arguments.
* Creates files 'postkontor.osm' og 'postkasser.osm'.

<code>python3 postbox2osm.py [--api]</code>

* This script will relocate post boxes which are inside buildings to outside the closest wall if the post box is close to the wall.
* The <code>--api</code> argument will load post boxes from the Posten api, otherwise it will load from 'postkasser.osm'.
* Creates the file 'postkasser_vegg.osm'. A 'DISTANCE' tag is added with the original distance in meters from the post box to the closest wall.

### References

* [Posten API](http://public.snws.posten.no/SalgsnettServicePublic.asmx).
* [Posten map of locations](https://www.posten.no/kart).
* [OpenStreetMap import plan](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Post_office_import_Norway).
