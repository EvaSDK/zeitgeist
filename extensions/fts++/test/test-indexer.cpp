/*
 * Copyright (C) 2012 Mikkel Kamstrup Erlandsen
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Authored by Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
 *
 */

#include <glib-object.h>

#include "stringutils.h"
#include "fts.h"
#include <zeitgeist-internal.h>

using namespace ZeitgeistFTS;

typedef struct
{
  ZeitgeistDbReader *db;
  ZeitgeistIndexer *indexer;
} Fixture;

static void setup    (Fixture *fix, gconstpointer data);
static void teardown (Fixture *fix, gconstpointer data);

static void
setup (Fixture *fix, gconstpointer data)
{
  // use in-memory databases for both zg db and fts db
  GError *error = NULL;
  g_setenv ("ZEITGEIST_DATABASE_PATH", ":memory:", TRUE);
  fix->db = ZEITGEIST_DB_READER (zeitgeist_engine_new (&error));

  if (error)
  {
    g_warning ("%s", error->message);
    return;
  }

  fix->indexer = zeitgeist_indexer_new (fix->db, &error);
  if (error)
  {
    g_warning ("%s", error->message);
    return;
  }
}

static void
teardown (Fixture *fix, gconstpointer data)
{
  zeitgeist_indexer_free (fix->indexer);
  g_object_unref (fix->db);
}

static ZeitgeistEvent* create_test_event1 (void)
{
  ZeitgeistEvent *event = zeitgeist_event_new ();
  ZeitgeistSubject *subject = zeitgeist_subject_new ();
  
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_RASTER_IMAGE);
  zeitgeist_subject_set_manifestation (subject, ZEITGEIST_NFO_REMOTE_DATA_OBJECT);
  zeitgeist_subject_set_uri (subject, "http://example.com/image.jpg");
  zeitgeist_subject_set_text (subject, "text");
  zeitgeist_subject_set_mimetype (subject, "image/png");

  zeitgeist_event_set_interpretation (event, ZEITGEIST_ZG_ACCESS_EVENT);
  zeitgeist_event_set_manifestation (event, ZEITGEIST_ZG_USER_ACTIVITY);
  zeitgeist_event_set_actor (event, "application://firefox.desktop");
  zeitgeist_event_add_subject (event, subject);

  g_object_unref (subject);
  return event;
}

static ZeitgeistEvent* create_test_event2 (void)
{
  ZeitgeistEvent *event = zeitgeist_event_new ();
  ZeitgeistSubject *subject = zeitgeist_subject_new ();
  
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_WEBSITE);
  zeitgeist_subject_set_manifestation (subject, ZEITGEIST_NFO_REMOTE_DATA_OBJECT);
  zeitgeist_subject_set_uri (subject, "http://example.com/I%20Love%20Wikis");
  zeitgeist_subject_set_text (subject, "Example.com Wiki Page. Kanji is awesome 漢字");
  zeitgeist_subject_set_mimetype (subject, "text/html");

  zeitgeist_event_set_interpretation (event, ZEITGEIST_ZG_ACCESS_EVENT);
  zeitgeist_event_set_manifestation (event, ZEITGEIST_ZG_USER_ACTIVITY);
  zeitgeist_event_set_actor (event, "application://firefox.desktop");
  zeitgeist_event_add_subject (event, subject);

  g_object_unref (subject);
  return event;
}

static ZeitgeistEvent* create_test_event3 (void)
{
  ZeitgeistEvent *event = zeitgeist_event_new ();
  ZeitgeistSubject *subject = zeitgeist_subject_new ();
  
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_WEBSITE);
  zeitgeist_subject_set_manifestation (subject, ZEITGEIST_NFO_REMOTE_DATA_OBJECT);
  // Greek IDN - stands for http://παράδειγμα.δοκιμή
  zeitgeist_subject_set_uri (subject, "http://xn--hxajbheg2az3al.xn--jxalpdlp/");
  zeitgeist_subject_set_text (subject, "IDNwiki");
  zeitgeist_subject_set_mimetype (subject, "text/html");

  zeitgeist_event_set_interpretation (event, ZEITGEIST_ZG_ACCESS_EVENT);
  zeitgeist_event_set_manifestation (event, ZEITGEIST_ZG_USER_ACTIVITY);
  zeitgeist_event_set_actor (event, "application://firefox.desktop");
  zeitgeist_event_add_subject (event, subject);

  g_object_unref (subject);
  return event;
}

static ZeitgeistEvent* create_test_event4 (void)
{
  ZeitgeistEvent *event = zeitgeist_event_new ();
  ZeitgeistSubject *subject = zeitgeist_subject_new ();
  
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_PRESENTATION);
  zeitgeist_subject_set_manifestation (subject, ZEITGEIST_NFO_FILE_DATA_OBJECT);
  zeitgeist_subject_set_uri (subject, "file:///home/username/Documents/my_fabulous_presentation.pdf");
  zeitgeist_subject_set_text (subject, NULL);
  zeitgeist_subject_set_mimetype (subject, "application/pdf");

  zeitgeist_event_set_interpretation (event, ZEITGEIST_ZG_MODIFY_EVENT);
  zeitgeist_event_set_manifestation (event, ZEITGEIST_ZG_USER_ACTIVITY);
  zeitgeist_event_set_actor (event, "application://libreoffice-impress.desktop");
  zeitgeist_event_add_subject (event, subject);

  g_object_unref (subject);
  return event;
}

// Steals the event, ref it if you want to keep it
static guint
index_event (Fixture *fix, ZeitgeistEvent *event)
{
  guint event_id = 0;

  // add event to DBs
  event_id = zeitgeist_engine_insert_event (ZEITGEIST_ENGINE (fix->db),
                                            event, NULL, NULL);

  GPtrArray *events = g_ptr_array_new_with_free_func (g_object_unref);
  g_ptr_array_add (events, event); // steal event ref
  zeitgeist_indexer_index_events (fix->indexer, events);
  g_ptr_array_unref (events);

  while (zeitgeist_indexer_has_pending_tasks (fix->indexer))
  {
    zeitgeist_indexer_process_task (fix->indexer);
  }

  return event_id;
}

static void
test_simple_query (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
 
  // add test events to DBs
  event_id = index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());
  index_event (fix, create_test_event3 ());
  index_event (fix, create_test_event4 ());

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              g_ptr_array_new (),
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  ZeitgeistSubject *subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "text");
}

static void
test_simple_with_filter (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;

  // add test events to DBs
  index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  zeitgeist_event_set_interpretation (event, ZEITGEIST_NFO_DOCUMENT);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (results->len, ==, 0);
  g_assert_cmpuint (matches, ==, 0);
}

static void
test_simple_with_valid_filter (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  event_id = index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  subject = zeitgeist_subject_new ();
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_IMAGE);
  zeitgeist_event_add_subject (event, subject);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "text");
}

static void
test_simple_negation (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  event_id = index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  subject = zeitgeist_subject_new ();
  zeitgeist_subject_set_interpretation (subject, "!" ZEITGEIST_NFO_IMAGE);
  zeitgeist_event_add_subject (event, subject);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, ==, 0);
  g_assert_cmpuint (results->len, ==, 0);
}

static void
test_simple_noexpand (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  event_id = index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  subject = zeitgeist_subject_new ();
  zeitgeist_subject_set_interpretation (subject, "+" ZEITGEIST_NFO_IMAGE);
  zeitgeist_event_add_subject (event, subject);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, ==, 0);
  g_assert_cmpuint (results->len, ==, 0);
}

static void
test_simple_noexpand_valid (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  event_id = index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  subject = zeitgeist_subject_new ();
  zeitgeist_subject_set_interpretation (subject, "+"ZEITGEIST_NFO_RASTER_IMAGE);
  zeitgeist_event_add_subject (event, subject);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "text",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "text");
}

static void
test_simple_url_unescape (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  index_event (fix, create_test_event1 ());
  event_id = index_event (fix, create_test_event2 ());

  GPtrArray *filters = g_ptr_array_new_with_free_func (g_object_unref);
  event = zeitgeist_event_new ();
  subject = zeitgeist_subject_new ();
  zeitgeist_subject_set_interpretation (subject, ZEITGEIST_NFO_WEBSITE);
  zeitgeist_event_add_subject (event, subject);
  g_ptr_array_add (filters, event); // steals ref

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "love",
                              zeitgeist_time_range_new_anytime (),
                              filters,
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "Example.com Wiki Page. Kanji is awesome 漢字");
}

static void
test_simple_cjk (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  index_event (fix, create_test_event1 ());
  event_id = index_event (fix, create_test_event2 ());

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "漢*",
                              zeitgeist_time_range_new_anytime (),
                              g_ptr_array_new (),
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "Example.com Wiki Page. Kanji is awesome 漢字");
}

static void
test_simple_idn_support (Fixture *fix, gconstpointer data)
{
  guint matches;
  guint event_id;
  ZeitgeistEvent* event;
  ZeitgeistSubject *subject;

  // add test events to DBs
  index_event (fix, create_test_event1 ());
  index_event (fix, create_test_event2 ());
  event_id = index_event (fix, create_test_event3 ());

  GPtrArray *results =
    zeitgeist_indexer_search (fix->indexer,
                              "παράδειγμα",
                              zeitgeist_time_range_new_anytime (),
                              g_ptr_array_new (),
                              0,
                              10,
                              ZEITGEIST_RESULT_TYPE_MOST_RECENT_EVENTS,
                              &matches,
                              NULL);

  g_assert_cmpuint (matches, >, 0);
  g_assert_cmpuint (results->len, ==, 1);

  event = (ZeitgeistEvent*) results->pdata[0];
  g_assert_cmpuint (zeitgeist_event_get_id (event), ==, event_id);

  subject = (ZeitgeistSubject*)
    g_ptr_array_index (zeitgeist_event_get_subjects (event), 0);
  g_assert_cmpstr (zeitgeist_subject_get_text (subject), ==, "IDNwiki");
}

G_BEGIN_DECLS

static void discard_message (const gchar *domain,
                             GLogLevelFlags level,
                             const gchar *msg,
                             gpointer userdata)
{
}

void test_indexer_create_suite (void)
{
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleQuery", Fixture, 0,
              setup, test_simple_query, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleWithFilter", Fixture, 0,
              setup, test_simple_with_filter, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleWithValidFilter", Fixture, 0,
              setup, test_simple_with_valid_filter, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleNegation", Fixture, 0,
              setup, test_simple_negation, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleNoexpand", Fixture, 0,
              setup, test_simple_noexpand, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/SimpleNoexpandValid", Fixture, 0,
              setup, test_simple_noexpand_valid, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/URLUnescape", Fixture, 0,
              setup, test_simple_url_unescape, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/IDNSupport", Fixture, 0,
              setup, test_simple_idn_support, teardown);
  g_test_add ("/Zeitgeist/FTS/Indexer/CJK", Fixture, 0,
              setup, test_simple_cjk, teardown);

  // get rid of the "rebuilding index..." messages
  g_log_set_handler (NULL, G_LOG_LEVEL_MESSAGE, discard_message, NULL);
}

G_END_DECLS
