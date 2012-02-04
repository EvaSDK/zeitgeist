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

#ifndef _ZGFTS_CONTROLLER_H_
#define _ZGFTS_CONTROLLER_H_

#include <glib-object.h>
#include <queue>
#include <vector>

#include "indexer.h"
#include "task.h"
#include "zeitgeist-internal.h"

namespace ZeitgeistFTS {

class Controller {
public:
  Controller (ZeitgeistDbReader *reader)
    : zg_reader (reader)
    , processing_source_id (0)
    , indexer (new Indexer (reader)) {};

  ~Controller ()
  {
    if (processing_source_id != 0)
      {
        g_source_remove (processing_source_id);
      }
  }

  void Initialize (GError **error);
  void Run ();
  void RebuildIndex ();
  void PushTask (Task* task);
  gboolean ProcessTask ();

  Indexer                 *indexer;

private:
  ZeitgeistDbReader       *zg_reader;

  typedef std::queue<Task*> TaskQueue;
  TaskQueue                queued_tasks;
  guint                    processing_source_id;
};

}

#endif /* _ZGFTS_CONTROLLER_H_ */
