/* zeitgeist-daemon.vala
 *
 * Copyright (C) 2011 Seif Lotfy <seif@lotfy.com>
 * Copyright (C) 2011 Collabora Ltd.
 *               By Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

public struct TimeRange {
	uint start;
	uint end;
}

[DBus (name = "org.gnome.zeitgeist.Log")]
public class Zeitgeist : Object {

	public Zeitgeist () {
		stdout.printf("Hi!\n");
	}

	// FIXME
	[DBus (signature = "a(asaasay)")]
	public Variant GetEvents (uint[] event_ids, BusName sender) {
		stdout.printf ("yeah!\n");
		//return new Variant("us", 5, "OK");
		return 1;
	}

	// FIXME
	public string[] FindRelatedUris (uint[] time_range,
			[DBus (signature = "a(asaasay)")] Variant event_templates,
			[DBus (signature = "a(asaasay)")] Variant result_event_templates,
			uint storage_state, uint num_events, uint result_type,
			BusName sender) {
		return new string[] { "hi", "bar" };
	}

	// FIXME
	public uint[] FindEventIds (uint[] time_range,
			[DBus (signature = "a(asaasay)")] Variant event_templates,
			uint storage_state, uint num_events, uint result_type,
			BusName sender) {
		return new uint[] { 1, 2, 3 };
	}

	// FIXME
	[DBus (signature = "a(asaasay)")]
	public uint[] FindEvents (uint[] time_range,
			[DBus (signature = "a(asaasay)")] Variant event_templates,
			uint storage_state, uint num_events, uint result_type,
			BusName sender) {
		return new uint[] { 1, 2, 3 };
	}

	// FIXME
	public uint[] InsertEvents (
			[DBus (signature = "a(asaasay)")] Variant events,
			BusName sender) {
		return new uint[] { 1, 2, 3 };
	}

	//FIXME
	public TimeRange DeleteEvents (uint[] event_ids, BusName sender) {
		return TimeRange() { start = 30, end = 40 };
	}

	// This is stupid. We don't need it.
	//public void DeleteLog ();

	public void Quit () {
		stdout.printf("BYE");
	}

	public void InstallMonitor (ObjectPath monitor_path,
			TimeRange time_range,
			[DBus (signature = "a(asaasay)")] Variant event_templates,
			BusName owner) {
		stdout.printf("i'll let you know!\n");
	}

	public void RemoveMonitor (ObjectPath monitor_path, BusName owner) {
		stdout.printf("bye my friend\n");
	}

	static void on_bus_aquired (DBusConnection conn) {
		try {
			conn.register_object (
				"/org/gnome/zeitgeist/log/activity",
				new Zeitgeist ());
		} catch (IOError e) {
			stderr.printf ("Could not register service\n");
		}
	}

	static void run () {
		// TODO: look at zeitgeist/singleton.py
		Bus.own_name (BusType.SESSION, "org.gnome.zeitgeist.Engine",
			BusNameOwnerFlags.NONE,
			on_bus_aquired,
			() => {},
			() => stderr.printf ("Could not aquire name\n"));
		new MainLoop ().run ();
	}

	static int main (string[] args) {
		var zeitgeist = new Zeitgeist ();
		zeitgeist.run ();
		return 0;
	}

}
