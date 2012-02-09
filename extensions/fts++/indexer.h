/*
 * Copyright (C) 2012 Canonical Ltd
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Authored by Michal Hruby <michal.hruby@canonical.com>
 *
 */

#ifndef _ZGFTS_INDEXER_H_
#define _ZGFTS_INDEXER_H_

#include <glib-object.h>
#include <gio/gio.h>
#include <xapian.h>

#include "zeitgeist-internal.h"

namespace ZeitgeistFTS {

const std::string INDEX_VERSION = "1";

class Indexer
{
public:
  typedef std::map<std::string, GAppInfo*> AppInfoMap;
  typedef std::set<std::string> ApplicationSet;

  Indexer (ZeitgeistDbReader *reader)
    : zg_reader (reader)
    , db (NULL)
    , query_parser (NULL)
    , enquire (NULL)
    , tokenizer (NULL)
    , clear_failed_id (0)
  {
    const gchar *home_dir = g_get_home_dir ();
    home_dir_path = home_dir != NULL ? home_dir : "/home";
  }

  ~Indexer ()
  {
    if (tokenizer) delete tokenizer;
    if (enquire) delete enquire;
    if (query_parser) delete query_parser;
    if (db) delete db;

    for (AppInfoMap::iterator it = app_info_cache.begin ();
         it != app_info_cache.end (); ++it)
    {
      g_object_unref (it->second);
    }

    if (clear_failed_id != 0)
    {
      g_source_remove (clear_failed_id);
    }
  }

  void Initialize (GError **error);
  bool CheckIndex ();
  void DropIndex ();
  void Commit ();

  void IndexEvent (ZeitgeistEvent *event);
  void DeleteEvent (guint32 event_id);
  void SetDbMetadata (std::string const& key, std::string const& value);

  GPtrArray* Search (const gchar *search,
                     ZeitgeistTimeRange *time_range,
                     GPtrArray *templates,
                     guint offset,
                     guint count,
                     ZeitgeistResultType result_type,
                     guint *matches,
                     GError **error);
  GPtrArray* SearchWithRelevancies (const gchar *search,
                                    ZeitgeistTimeRange *time_range,
                                    GPtrArray *templates,
                                    guint offset,
                                    guint count,
                                    ZeitgeistResultType result_type,
                                    gdouble **relevancies,
                                    gint *relevancies_size,
                                    guint *matches,
                                    GError **error);

private:
  std::string ExpandType (std::string const& prefix, const gchar* unparsed_uri);
  std::string CompileEventFilterQuery (GPtrArray *templates);
  std::string CompileTimeRangeFilterQuery (gint64 start, gint64 end);
  std::string CompileQueryString (const gchar *search,
                                  ZeitgeistTimeRange *time_range,
                                  GPtrArray *templates);

  void AddDocFilters (ZeitgeistEvent *event, Xapian::Document &doc);
  void IndexText (std::string const& text);
  void IndexUri (std::string const& uri, std::string const& origin);
  bool IndexActor (std::string const& actor, bool is_subject);

  gboolean ClearFailedLookupsCb ();

  ZeitgeistDbReader        *zg_reader;
  Xapian::WritableDatabase *db;
  Xapian::QueryParser      *query_parser;
  Xapian::Enquire          *enquire;
  Xapian::TermGenerator    *tokenizer;
  AppInfoMap                app_info_cache;
  ApplicationSet            failed_lookups;

  guint                     clear_failed_id;
  std::string               home_dir_path;
};

}

#endif /* _ZGFTS_INDEXER_H_ */
