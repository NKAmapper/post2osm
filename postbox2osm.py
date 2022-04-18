#!/usr/bin/env python3
# -*- coding: utf8

# post2osm
# Converts post boxes from Posten api to osm format for import/update
# Usage: python post2osm.py [-api]
# Argument "-api" will load post boxes from Posten APi, otherwise loads from file postkasser.osm.
# Creats output files postkasser_vegg.osm'


import html
import sys
import os
import json
import math
import urllib.request
from xml.etree import ElementTree


version = "1.0.0"

import_folder = "~/Jottacloud/osm/bygninger/"  # Folder containing import building files (default folder tried first)

wall_threshold = 5  # Meters (post boxes only relocated if less than x meters from closest wall)

wall_offset = 1  # Meters (post boxes relocated x meters ouside of closest wall)



def message (output_text):
	'''
	Output message to console.
	'''

	sys.stdout.write (output_text)
	sys.stdout.flush()



def line_distance(s1, s2, p3, offset):
	'''
	Compute closest intersection and distance from point p3 to line segment [s1, s2].
	Works for short distances.
	Offset puts the intersection beyond or in front of line segment by given meters.
	'''

	x1, y1, x2, y2, x3, y3 = map(math.radians, [s1[0], s1[1], s2[0], s2[1], p3[0], p3[1]])

	# Simplified reprojection of latitude
	x1 = x1 * math.cos( y1 )
	x2 = x2 * math.cos( y2 )
	x3 = x3 * math.cos( y3 )

	A = x3 - x1
	B = y3 - y1
	dx = x2 - x1
	dy = y2 - y1

	dot = (x3 - x1)*dx + (y3 - y1)*dy
	len_sq = dx*dx + dy*dy

	if len_sq != 0:  # in case of zero length line
		param = dot / len_sq
	else:
		param = -1

	if param < 0:
		x4 = x1
		y4 = y1
	elif param > 1:
		x4 = x2
		y4 = y2
	else:
		x4 = x1 + param * dx
		y4 = y1 + param * dy

	# Also compute distance from p to segment

	x = x4 - x3
	y = y4 - y3
	distance = 6371000 * math.sqrt( x*x + y*y )  # In meters

	# Add offset to line intersection (omit this section if offset is not needed)

	x4 = x3 + x * (1 + offset / distance)
	y4 = y3 + y * (1 + offset / distance)

	# Project back to longitude/latitude

	x4 = x4 / math.cos(y4)

	lon = math.degrees(x4)
	lat = math.degrees(y4)

	return ((lon, lat), distance)



def closest_line(point, polygon):
	'''
	Get closest point on polygon, including multipolygons.
	'''

	best_distance = 99999
	best_point = None

	for patch in polygon:
		for i in range(1, len(patch)):
			new_point, dist = line_distance(patch[i-1], patch[i], point, wall_offset)
			if dist < best_distance:
				best_distance = dist
				best_point = new_point

	return (best_point, best_distance)




def inside_polygon (point, polygon):
	'''
	Tests whether point (x,y) is inside a polygon
	Ray tracing method
	'''

	if polygon[0] == polygon[-1]:
		x, y = point
		n = len(polygon)
		inside = False

		p1x, p1y = polygon[0]
		for i in range(n):
			p2x, p2y = polygon[i]
			if y > min(p1y, p2y):
				if y <= max(p1y, p2y):
					if x <= max(p1x, p2x):
						if p1y != p2y:
							xints = (y-p1y) * (p2x-p1x) / (p2y-p1y) + p1x
						if p1x == p2x or x <= xints:
							inside = not inside
			p1x, p1y = p2x, p2y

		return inside

	else:
		return None



def load_municipalities():
	'''
	Load dict of all municipalities
	'''

	url = "https://ws.geonorge.no/kommuneinfo/v1/fylkerkommuner?filtrer=fylkesnummer%2Cfylkesnavn%2Ckommuner.kommunenummer%2Ckommuner.kommunenavnNorsk"
	file = urllib.request.urlopen(url)
	data = json.load(file)
	file.close()
	for county in data:
		for municipality in county['kommuner']:
			entry = {
				'ref': municipality['kommunenummer'],
				'name': municipality['kommunenavnNorsk'],
				'county': county['fylkesnavn']
			}
			municipalities.append(entry)



def get_tag(node, tag):
	'''
	Get value of tag from XML.
	'''

	t = node.find("tag[@k='%s']" % tag)
	if t is not None:
		return t.get('v')
	else:
		return None



def make_osm_line(key,value):
	'''
	Produce a tag for OSM file
	'''

	if value != None:
		value = html.unescape(value)
		encoded_value = html.escape(value).strip()
		if encoded_value:
			file.write ('    <tag k="%s" v="%s" />\n' % (key, encoded_value))



def opening_hours(hours_csv):
	'''
	Generate opening hours in osm format.
	Input format from Posten api: "Man.–fre. 08.00–22.00, Lør. 08.00–20.00"
	'''

	day_conversion = {
		'man': 'Mo',
		'tir': 'Tu',
		'ons': 'We',
		'tor': 'Th',
		'fre': 'Fr',
		'lør': 'Sa',
		'søn': 'Su'}

	if hours_csv != None:

		hours_csv = hours_csv.lower()
		hours_csv = hours_csv.replace("–","-").replace(".-","-").replace(". "," ").replace(" - ","-").replace(":","").replace(".",":")

		for day_in, day_out in day_conversion.items():
			hours_csv = hours_csv.replace(day_in, day_out)

		hours_csv = hours_csv.replace("00:01","00:00").replace("23:58","24:00").replace("23:59","24:00")

		hours = []
		for day in hours_csv.split(", "):
			if "00:00-00:00" not in day:
				hours.append(day)

		result = ", ".join(hours)

		if result == "Mo-Su 00:00-24:00" or result == "Mo-Su døgnåpent":
			result = "24/7"

		return result

	else:
		return ""




def load_mailbox_file():
	'''
	Load post boxes from OSM file produced by post2osm.py and store in list.
	'''

	message ("Load mail boxes from OSM file ...\n")

	file = open("postkasser.osm")
	tree = ElementTree.parse(file)
	file.close()

	root = tree.getroot()
	for node in root:

		latitude = float(node.attrib['lat'])
		longitude = float(node.attrib['lon'])
		
		entry = {
			'ref':			get_tag(node,'ref:posten_box'),
			'point':		(longitude, latitude),
			'address':		get_tag(node, 'ADDRESS'),
			'municipality':	get_tag(node, 'MUNICIPALITY'),
			'location':		get_tag(node, 'LOCATION'),
			'collection':	get_tag(node, 'collection_times')
		}
		post_boxes.append(entry)

	message ("\t%i post boxes loaded\n" % len(post_boxes))



def load_mailbox_api():
	'''
	Load post boxes from Posten api and store in list.
	'''

	message ("Load mail boxes from Posten api ...\n")

	# Load api

	url = "http://public.snws.posten.no/SalgsnettServicePublic.asmx/GetInnleveringspostkasser?searchValue="

	request = urllib.request.Request(url)
	file = urllib.request.urlopen(request)
	tree = ElementTree.parse(file)
	file.close()

	ns = {'ns0': 'https://public.snws.posten.no/SalgsnettService.asmx/'}  # Namespace

	root = tree.getroot()

	# Iterate all mail boxes and produce OSM tags

	for box in root.iterfind('ns0:EnhetDTO', ns):

		if box.find('ns0:PostnrBesoksadresse/ns0:Land/ns0:Kode', ns) != None and \
				box.find('ns0:Status/ns0:Navn', ns).text == "Aktiv":

			latitude = box.find('ns0:Latitude', ns).text
			longitude = box.find('ns0:Longitude', ns).text
			if (latitude[0] == "-") or (longitude[0] == "-"):
				latitude = "0"
				longitude = "0"

			ref = box.find('ns0:Enhetsnr', ns).text

#			operator = box.find('ns0:ConnectedOffice/ns0:EnhetsNavn', ns)  # Responsible post office (data not complete)
#			if operator != None:
#				make_osm_line ("operator", operator.text)

			# Get address

			address = box.find('ns0:PostnrBesoksadresse', ns)

			street = box.find('ns0:Besoksadresse', ns).text
			if street != None:
				address_line = street.strip() + ", "
			else:
				address_line = ""
			address_line += address.find('ns0:Postnr', ns).text.strip() + " " + address.find('ns0:Poststed', ns).text

			municipality_name = address.find('ns0:Kommune', ns).text
#			county = address.find('ns0:Fylke', ns).text
			location = box.find('ns0:Beliggenhet', ns).text

			# Get collection time

			collection_times = None
			if box.find('ns0:Frister', ns):
				collection = box.find('ns0:Frister/ns0:FristDTO', ns)
				hours = collection.find("ns0:Periode", ns).text + " " + collection.find('ns0:Klokkeslett', ns).text
				collection_times = opening_hours(hours)

			# Discover any new box type

			box_type = box.find('ns0:EnhetsType/ns0:EnhetsType', ns).text
			if box_type != "10":  # Post box
				message ("\tUnknown type: '%s'\n" % box_type)

			entry = {
				'ref':			ref,
				'point':		(float(longitude), float(latitude)),
				'address':		address_line,
				'municipality':	municipality_name,
				'location':		location,
				'collection':	collection_times
			}
			post_boxes.append(entry)

	message ("\t%i post boxes loaded\n" % len(post_boxes))



def check_mailbox():
	'''
	Check if mailbox should be relocated outside of building.
	If distance to the closest wall is less than given threshold, the mailbox will be relocated to x meters outside of closest wall. 
	'''

	translate_county= {
		'Møre og Romsdal': 'M.R.',
		'Nordland': 'N.',
		'Innlandet': 'INNLANDET',
		'Viken': 'VIKEN'
	}

	message("Moving post boxes to closest wall ...\n")

	total_moved = 0

	for municipality in municipalities:

		# Load building file for municipality

		message ("\t%-20s" % municipality['name'])

		name = municipality['name'].upper()
		if municipality['name'] in ['Våler', 'Herøy']:
			name += " (%s)" % translate_county[ municipality['county'] ]

		filename = "bygninger_%s_%s.geojson" % (municipality['ref'], municipality['name'].replace(" ", "_"))
		file_path = os.path.expanduser(import_folder + filename)

		file = open(file_path)
		buildings = json.load(file)
		file.close()

		count_box = 0
		count_moved = 0
		count_polygons = 0

		# Create bbox for each building which has polygon (used for filtering later)

		for building in buildings['features']:
			if building['geometry']['type'] == "Polygon":
				building['min_bbox'] = (min([ node[0] for node in building['geometry']['coordinates'][0] ]), \
										min([ node[1] for node in building['geometry']['coordinates'][0] ]))

				building['max_bbox'] = (max([ node[0] for node in building['geometry']['coordinates'][0] ]), \
										max([ node[1] for node in building['geometry']['coordinates'][0] ]))	
				count_polygons += 1

		if count_polygons == 0:
			message ("No building polygons\n")
			continue

		buildings = [building for building in buildings['features'] if 'min_bbox' in building]

		# Loop each box and identify any building around it

		for box in post_boxes:
			if box['municipality'] == name:
				count_box += 1

				# Check if post box is inside a building

				for building in buildings:

					if building['min_bbox'][0] < box['point'][0] < building['max_bbox'][0] and \
							building['min_bbox'][1] < box['point'][1] < building['max_bbox'][1] and \
							inside_polygon(box['point'], building['geometry']['coordinates'][0]):

						point, distance = closest_line(box['point'], building['geometry']['coordinates'])
						box['distance'] = "%.1f" % distance
						if distance < wall_threshold:

							# Check if point is inside another building (if so, abort the relocation)

							still_inside = False

							for building2 in buildings:
								if building2['min_bbox'][0] < point[0] < building2['max_bbox'][0] and \
										building2['min_bbox'][1] < point[1] < building2['max_bbox'][1] and \
										inside_polygon(point, building2['geometry']['coordinates'][0]):
									still_inside = True
									break

							if not still_inside:
								box['point'] = point
								count_moved += 1
								total_moved += 1
								break

		message ("%i of %i post boxes moved\n" % (count_moved, count_box))

	message ("\tTotal %i of %i post boxes moved\n" % (total_moved, len(post_boxes)))



def save_mailbox():
	'''
	Save mailboxes to OSM file.
	'''

	global file

	message ("Save mail boxes ...\n")

	# Produce OSM file header

	filename = "postkasser_vegg.osm"
	file = open(filename, "w")

	file.write ('<?xml version="1.0" encoding="UTF-8"?>\n')
	file.write ('<osm version="0.6" generator="postbox2osm v%s" upload="false">\n' % version)

	node_id = -1000

	# Iterate all mail boxes and produce OSM tags

	for box in post_boxes:

		node_id -= 1

		longitude = round(box['point'][0], 7)
		latitude = round(box['point'][1], 7)

		file.write ('  <node id="%i" lat="%f" lon="%f">\n' % (node_id, latitude, longitude))

		if latitude < 57:
			make_osm_line ("GEOCODE", "yes")

		make_osm_line ("amenity", "post_box")
		make_osm_line ("ref:posten_box", box['ref'])
		make_osm_line ("brand", "Posten")

		if box['collection']:
			make_osm_line ("collection_times", box['collection'])

		make_osm_line ("ADDRESS", box['address'])
		make_osm_line ("LOCATION", box['location'])

		if "distance" in box:
			make_osm_line ("DISTANCE", box['distance'])

		file.write ('  </node>\n')

	# Wrap up

	file.write ('</osm>\n')
	file.close()

	message ("\t%i post boxes saved to '%s'\n\n" % (len(post_boxes), filename))



# Main program

if __name__ == '__main__':

	municipalities = []
	post_boxes = []

	load_municipalities()

	if "--api" in sys.argv:
		load_mailbox_api()
	else:
		load_mailbox_file()

	check_mailbox()
	save_mailbox()
