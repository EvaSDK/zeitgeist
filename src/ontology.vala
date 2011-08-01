/* datamodel.vala
 *
 * Copyright © 2011 Collabora Ltd.
 *             By Seif Lotfy <seif@lotfy.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

public class Symbol
{
    private static HashTable<string, Symbol> all_symbols = null;
    private List<string> parents;
    private List<string> children;
    public string uri { get; private set; }
    public string display_name { get; private set; }
    
    private Symbol(string uri, string display_name, string[] parents,string[] children){
        this.uri = uri;
        this.display_name = display_name;
        this.parents = new List<string>();
        for (int i = 0; i < parents.length; i++)
            this.parents.append(parents[i]);
        this.children = new List<string>();
        for (int i = 0; i < children.length; i++)
            this.children.append(children[i]);
    }
    
    public static List<string> get_all_parents(string symbbol_uri)
    {
        var symbol = all_symbols.lookup(symbbol_uri);
        var results = new List<string>();
        foreach (string uri in symbol.parents)
        {
            results.append(uri);
            var parent = all_symbols.lookup(uri);
            // Recursivly get the other parents
            foreach (string s in get_all_parents(uri))
                if (results.index(s) > -1)
                    results.append(s);
        }
        return results;
    }
    
    public static List<string> get_all_children(string symbbol_uri)
    {
        var symbol = all_symbols.lookup(symbbol_uri);
        var results = new List<string>();
        foreach (string uri in symbol.children)
        {
            results.append(uri);
            var child = all_symbols.lookup(uri);
            // Recursivly get the other children
            foreach (string s in child.get_all_children(uri))
                if (results.index(s) > -1)
                    results.append(s);
        }
        return results;
    }
    
    public static bool is_a(string symbol_uri, string parent_uri)
    {
        foreach (string uri in get_all_parents(symbol_uri))
            if (parent_uri == uri)
                return true;
        return false;
    }
    
    public string to_string()
    {
        return this.uri;
    }
    
    public static void register(string uri, string display_name, string[] parents,
                                string[] children)
    {
        if (all_symbols == null)
            all_symbols = new HashTable<string, Symbol>(str_hash, str_equal);
        Symbol symbol = new Symbol(uri, display_name, parents, children);
        all_symbols.insert(uri, symbol);
    }
    
    public static Symbol from_uri(string uri)
    {
        return all_symbols.lookup(uri);
    }
}
