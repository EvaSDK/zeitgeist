/* indexer.vapi is hand-written - not a big deal for these ~10 lines */

namespace Zeitgeist {
  [Compact]
  [CCode (free_function = "zeitgeist_indexer_free", cheader_filename = "indexer.h")]
  public class Indexer {
    public Indexer (DbReader reader) throws EngineError;

    public GLib.GenericArray<Event> search (string search_string,
                                            TimeRange time_range,
                                            GLib.GenericArray<Event> templates,
                                            uint offset,
                                            uint count,
                                            ResultType result_type) throws GLib.Error;
  }
}
