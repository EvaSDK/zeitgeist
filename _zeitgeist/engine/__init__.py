import os
import logging
from xdg import BaseDirectory

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("zeitgeist.engine")

DB_PATH = os.path.join(BaseDirectory.save_data_path("zeitgeist"),
	"database.sqlite")

AVAILABLE_ENGINES = ["querymancer", "storm"]
ENGINE_FALLBACK = AVAILABLE_ENGINES[0]

def get_engine_type():
	""" Returns the value of the $ZEITGEIST_ENGINE environment variable or,
	if it isn't defined, the default engine."""
	value = os.environ.get("ZEITGEIST_ENGINE")
	if value == "default":
		value = None
	if value and value not in AVAILABLE_ENGINES:
		raise RuntimeError("Unknown engine type requested: \"%s\"." % value)
	return value if value else ENGINE_FALLBACK

_engine = None
def create_engine(engine_type=None):
	""" Creates an engine instance of the type defined by 'engine_type'.
	If 'engine_type' is None 'ENGINE_FALLBACK' is used.
	This function looks at _zeitgeist.engine to find the engine implementation.
	Each engine implementation has to follow the following conventions:
		1.) it has to be in _zeitgeist/engine/SOMENAME_engine.py
			(where SOMENAME defines the type)
		2.) the name of the class has to be ZeitgeistEngine and the class
			itself has to be a sublass of _zeitgeist.engine.engine_base.BaseEngine
	"""	
	global _engine
	if engine_type is None:
		engine_type = ENGINE_FALLBACK
	engine_type = engine_type.lower()		
	
	# See if we can reuse _engine
	if _engine and not _engine.is_closed():
		running_type = _engine.__module__.split(".").pop().lower()
		if not running_type == engine_type:
			raise RuntimeError(
				("There is already a zeitgeist engine running. But this "
				 "engine has another than the requested type "
				 "(requested='%s', running='%s')" %(engine_type, running_type))
			)
		return _engine
	try:
		log.debug("Creating engine '%s'" % engine_type)
		engine_cls = __import__(
			"_zeitgeist.engine.%s_engine" %engine_type,
			globals(), locals(), ["ZeitgeistEngine",], -1
		)
	except ImportError, err:
		logging.exception("Could not load engine implementation for %r" % engine_type)
		raise
	_engine = engine_cls.ZeitgeistEngine()
	return _engine

def get_default_engine():
	""" Get the running engine instance or create a new one. """
	if _engine is None or _engine.is_closed() :
		return create_engine(engine_type=get_engine_type())
	return _engine
