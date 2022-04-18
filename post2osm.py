#!/usr/bin/env python3
# -*- coding: utf8

# post2osm
# Converts post offices, parcel lockers and post boxes from Posten api to osm format for import/update
# Usage: python post2osm.py
# Creats output files 'postkontor.osm' and 'postkasser.osm'


import html
import sys
import urllib.request
from xml.etree import ElementTree


version = "1.2.0"


transform_name = [
	('MENY', 'Meny'),
	('REMA', 'Rema'),
	('KIWI', 'Kiwi'),
	('EUROSPAR', 'Eurospar'),
	('SPAR', 'Spar'),
	('AMFI', 'Amfi'),
	('AS', ''),
	('As ', ''),
	('A/L', ''),
	('BYGG', 'Bygg'),
	('Sentrum', 'sentrum'),
	('- avd. Roan', ''),
	('Eftf', 'eftf'),
	('Handelslag', 'handelslag'),
	('Handelskompani', 'handelskompani'),
	('Service Senter', 'servicenter'),
	('Servicenter', 'servicenter'),
	('Bilsenter As', 'bilsenter'),
	('Storsenter', 'storsenter'),
	('Verk', 'verk'),
	('Maze', 'Máze'),
	(' - ', ', '),
	(' I ', ' i ')
]


def message (output_text):
	'''
	Output message to console.
	'''

	sys.stdout.write (output_text)
	sys.stdout.flush()



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



def process_post_offices():
	'''
	Load post offices and parcel lockers from Posten api and produce osm file.
	'''

	global file

	message ("\nGenerate post offices and parcel lockers ...\n")

	# Load api

	url = "http://public.snws.posten.no/SalgsnettServicePublic.asmx/GetEnheterByLandkode?searchValue=&landkode=NO"

	request = urllib.request.Request(url)
	file = urllib.request.urlopen(request)
	tree = ElementTree.parse(file)
	file.close()

	ns = {'ns0': 'https://public.snws.posten.no/SalgsnettService.asmx/'}  # Namespace

	root = tree.getroot()

	# Produce OSM file header

	filename = "postkontor.osm"
	file = open(filename, "w")

	file.write ('<?xml version="1.0" encoding="UTF-8"?>\n')
	file.write ('<osm version="0.6" generator="post2osm v%s" upload="false">\n' % version)

	node_id = -1000
	count_total = 0
	count_lockers = 0

	# Iterate all post offices and produce OSM tags

	for office in root.iterfind('ns0:EnhetDTO', ns):

		if office.find('ns0:PostnrBesoksadresse/ns0:Land/ns0:Kode', ns) != None and \
				office.find('ns0:PostnrBesoksadresse/ns0:Land/ns0:Kode', ns).text == "NO" and \
				office.find('ns0:Status/ns0:Navn', ns).text == "Aktiv" and \
				office.find('ns0:EnhetsType/ns0:EnhetsType', ns).text != "36":  # Avoid pilot automats

			node_id -= 1
			count_total += 1

			latitude = office.find('ns0:Latitude', ns).text
			longitude = office.find('ns0:Longitude', ns).text
			if (latitude[0] == "-") or (longitude[0] == "-"):
				latitude = "0"
				longitude = "0"

			file.write ('  <node id="%i" lat="%s" lon="%s">\n' % (node_id, latitude, longitude))

			if float(latitude) < 57:
				make_osm_line ("GEOCODE", "yes")

			make_osm_line ("ref:posten", office.find('ns0:Enhetsnr', ns).text)
			make_osm_line ("brand", "Posten")

			# Get address

			address = office.find('ns0:PostnrBesoksadresse', ns)

			street = office.find('ns0:Besoksadresse', ns).text
			if street != None:
				address_line = street.strip() + ", "
			else:
				address_line = ""
			address_line += address.find('ns0:Postnr', ns).text.strip() + " " + address.find('ns0:Poststed', ns).text

			make_osm_line ("ADDRESS", address_line)
#			make_osm_line ("MUNICIPALITY", address.find('ns0:Kommune', ns).text)
#			make_osm_line ("COUNTY", address.find('ns0:Fylke', ns).text)
			make_osm_line ("LOCATION", office.find('ns0:Beliggenhet', ns).text)			

			# Adjust name and operator according to type of post office

			office_type = office.find('ns0:EnhetsType/ns0:EnhetsType', ns).text
			name = office.find('ns0:EnhetsNavn', ns).text
			operator = office.find('ns0:Navn', ns).text

			for word_from, word_to in transform_name:
				name = name.replace(word_from, word_to)
				operator = operator.replace(word_from, word_to)

			if "kiwi" in operator.lower():
				for number in ['0','1','2','3','4','5','6','7','8','9']:
					operator = operator.replace(number, '')

			name = name.replace("  "," ").strip()
			operator = operator.replace("  "," ").strip()
			alt_name = ""

			# Tag according to type of post office / locker

			if office_type == "21":  # Postkontor
				operator = "Posten"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "bureau")				

			elif office_type == "1":  # Bedriftsenter
				operator = "Posten"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "bureau")

			elif office_type == "4":  # Post i butikk
				name = name.replace("Post i Butikk", "post i butikk")
				alt_name = operator + " post i butikk"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "post_annex")

			elif office_type == "19":  # Pakkeutlevering
				name = name.replace("Posten ", "")
				alt_name = operator + " pakkeutlevering"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "post_partner")

			elif office_type == "32":  # Postpunkt (operated by Posten)
				operator = "Posten"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "bureau")

			elif office_type == "33":  # Postpunkt
				alt_name = operator + " postpunkt"
				make_osm_line ("amenity", "post_office")
				make_osm_line("post_office", "post_annex")

#			elif office_type == "36":  # Pakkeautomat (not used anymore?)
#				name = name.replace('Post i Butikk', 'post i butikk')
#				operator = ""
#				make_osm_line ("amenity", "parcel_locker")
#				make_osm_line("post_office:type", "parcel_automat")

			elif office_type == "37":  # Pakkeboks
				operator = "Posten"
				make_osm_line ("amenity", "parcel_locker")
				count_lockers += 1

			else:
				make_osm_line ("amenity", "post_office")
				make_osm_line ("FIXME", "Unknown type: '%s'" % office_type)
				message ("\tUnknown type: '%s'\n" % office_type)

			make_osm_line ("name", name)

			if alt_name and (alt_name != name):
				make_osm_line ("alt_name", alt_name)

			make_osm_line("operator", operator)

			# Opening hours

			for opening in office.iterfind('ns0:Apningstider/ns0:ApningstidDTO', ns):
				if opening.find('ns0:ApningstidType', ns) != None and opening.find('ns0:ApningstidType', ns).text == "1000":
					hours = opening.find('ns0:ApningstidCSV', ns).text
#					make_osm_line("HOURS", "%s" % hours)
					make_osm_line("opening_hours", opening_hours(hours))
					break

			# Wheelchair (data not complete)

#			for service in office.iterfind('ns0:Tjenester/ns0:TjenesteDTO', ns):
#				if "rullestol" in service.find('ns0:Navn', ns).text:
#					make_osm_line ("wheelchair", "yes")

			file.write ('  </node>\n')

	# Wrap up

	file.write ('</osm>\n')
	file.close()

	message ("\t%i post offices and %i parcel lockers saved to '%s'\n" % (count_total - count_lockers, count_lockers, filename))



def process_mailbox():
	'''
	Load post boxes from Posten api and produce osm file.
	'''

	global file

	message ("Generate mail boxes ...\n")

	# Load api

	url = "http://public.snws.posten.no/SalgsnettServicePublic.asmx/GetInnleveringspostkasser?searchValue="

	request = urllib.request.Request(url)
	file = urllib.request.urlopen(request)
	tree = ElementTree.parse(file)
	file.close()

	ns = {'ns0': 'https://public.snws.posten.no/SalgsnettService.asmx/'}  # Namespace

	root = tree.getroot()

	# Produce OSM file header

	filename = "postkasser.osm"
	file = open(filename, "w")

	file.write ('<?xml version="1.0" encoding="UTF-8"?>\n')
	file.write ('<osm version="0.6" generator="post2osm v%s" upload="false">\n' % version)

	node_id = -1000
	count = 0

	# Iterate all mail boxes and produce OSM tags

	for box in root.iterfind('ns0:EnhetDTO', ns):

		if box.find('ns0:PostnrBesoksadresse/ns0:Land/ns0:Kode', ns) != None and \
				box.find('ns0:Status/ns0:Navn', ns).text == "Aktiv":

			node_id -= 1
			count += 1

			latitude = box.find('ns0:Latitude', ns).text
			longitude = box.find('ns0:Longitude', ns).text
			if (latitude[0] == "-") or (longitude[0] == "-"):
				latitude = "0"
				longitude = "0"

			file.write ('  <node id="%i" lat="%s" lon="%s">\n' % (node_id, latitude, longitude))

			if float(latitude) < 57:
				make_osm_line ("GEOCODE", "yes")

			make_osm_line ("amenity", "post_box")
			make_osm_line ("ref:posten_box", box.find('ns0:Enhetsnr', ns).text)
			make_osm_line ("brand", "Posten")

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

			make_osm_line ("ADDRESS", address_line)
			make_osm_line ("MUNICIPALITY", address.find('ns0:Kommune', ns).text)
#			make_osm_line ("COUNTY", address.find('ns0:Fylke', ns).text)
			make_osm_line ("LOCATION", box.find('ns0:Beliggenhet', ns).text)	

			# Get collection time

			if box.find('ns0:Frister', ns):
				collection = box.find('ns0:Frister/ns0:FristDTO', ns)
				hours = collection.find("ns0:Periode", ns).text + " " + collection.find('ns0:Klokkeslett', ns).text
				make_osm_line ("collection_times", opening_hours(hours))

			# Discover any new box type

			box_type = box.find('ns0:EnhetsType/ns0:EnhetsType', ns).text
			if box_type != "10":  # Post box
				make_osm_line ("FIXME", "Unknown type: '%s'" % box_type)
				message ("\tUnknown type: '%s'\n" % box_type)

			file.write ('  </node>\n')

	# Wrap up

	file.write ('</osm>\n')
	file.close()

	message ("\t%i post boxes saved to '%s'\n\n" % (count, filename))



# Main program

if __name__ == '__main__':
	process_post_offices()
	process_mailbox()
