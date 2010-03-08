# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Markus Korn <thekorn@gmx.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from rdflib.syntax.serializers.RecursiveSerializer import RecursiveSerializer
from rdflib import RDF, RDFS
from rdflib.Namespace import Namespace

NIENS = Namespace("http://www.semanticdesktop.org/ontologies/2007/01/19/nie#")

import pprint

def make_symbol_name(name):
	def _iter_chars(text):
		yield text[0]
		for s in text[1:]:
			if s.isupper():
				yield "_"
			yield s
	name = "".join(_iter_chars(name))
	return name.upper()

def sort_enum(value):
	try:
		return int(value[0].split("_")[-1])
	except ValueError:
		return 0

class PythonSerializer(RecursiveSerializer):

	def _create_symbol_collection(self, stream, collection_type):
		collection_name = str(collection_type).split("#")[-1]
		comments = list(self.store.objects(collection_type, RDFS.comment))
		doc = comments[0] if comments else ""
		labels = list(self.store.objects(collection_type, RDFS.label))
		display_name = labels[0] if labels else collection_name
		stream.write("%s = SymbolCollection('%s', '%s')\n" %(collection_name, display_name, doc))
		return collection_name

	def _create_symbol(self, stream, collection_name, member):
		name = str(member).split("#")[-1]
		comments = list(self.store.objects(member, RDFS.comment))
		doc = comments[0] if comments else ""
		labels = list(self.store.objects(member, RDFS.label))
		display_name = labels[0] if labels else name
		#TODO: displayname, how are translation handled? on trig level or on python level?
		stream.write(("register_symbol(collection=%s, name='%s',\n"
					  "\turi='%s',\n"
					  "\tdisplayname=_('%s'),\n"
					  "\tdocstring='%s')\n") %(collection_name, make_symbol_name(name), member, display_name, doc))

	def _create_enum(self, stream, enum):
		enum_name = str(enum).split("#")[-1]
		comments = list(self.store.objects(enum, RDFS.comment))
		doc = comments[0] if comments else ""
		stream.write("%s = Enum('%s')\n" %(enum_name, doc))
		return enum_name

	def _create_enum_value(self, stream, enum_name, value, label, docstring):
		stream.write("register_enum(%s, %d, '%s', '%s')\n" %(enum_name, int(value.split("_")[-1]), label, docstring))

	def serialize(self, stream, base=None, encoding=None, **args):
		#~ # this is not working yet, and does not do anything
		#~ for resource in self.store.subjects(RDFS.subClassOf, RDFS.Resource):
			#~ #stream.write("""class %s(RDFSResource):\n\tpass\n\n""" %str(resource).split("#")[-1])
#~ 
			#~ for member in self.store.subjects(RDFS.domain, resource):
				#~ attributes = dict(self.store.predicate_objects(member))
				#~ if attributes.pop(RDF.type) == RDFS.RDFSNS["Property"]:
					#~ # ok, it is a property
					#~ name = attributes.pop(RDFS.label)
					#~ print name
					#~ print attributes
				#~ else:
					#~ raise ValueError
				#~ break

		for collection_types in (NIENS["InformationElement"], NIENS["DataObject"]):
			for collection_type in self.store.subjects(RDFS.subClassOf, collection_types):
				stream.write("\n#%s\n\n" %str(collection_type).split("#")[-1])
				collection_name = self._create_symbol_collection(stream, collection_type)
				for member in sorted(self.store.subjects(RDFS.subClassOf, collection_type)):
					self._create_symbol(stream, collection_name, member)
