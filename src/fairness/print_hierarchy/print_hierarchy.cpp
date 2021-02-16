/*****************************************************************************\
 *  Copyright (c) 2020 Lawrence Livermore National Security, LLC.  Produced at
 *  the Lawrence Livermore National Laboratory (cf, AUTHORS, DISCLAIMER.LLNS).
 *  LLNL-CODE-658032 All rights reserved.
 *
 *  This file is part of the Flux resource manager framework.
 *  For details, see https://github.com/flux-framework.
 *
 *  This program is free software; you can redistribute it and/or modify it
 *  under the terms of the GNU General Public License as published by the Free
 *  Software Foundation; either version 2 of the license, or (at your option)
 *  any later version.
 *
 *  Flux is distributed in the hope that it will be useful, but WITHOUT
 *  ANY WARRANTY; without even the IMPLIED WARRANTY OF MERCHANTABILITY or
 *  FITNESS FOR A PARTICULAR PURPOSE.  See the terms and conditions of the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License along
 *  with this program; if not, write to the Free Software Foundation, Inc.,
 *  59 Temple Place, Suite 330, Boston, MA 02111-1307 USA.
 *  See also:  http://www.gnu.org/licenses/
\*****************************************************************************/

#include <iostream>

#include "src/fairness/weighted_tree/test/load_accounting_db.hpp"

using namespace Flux::accounting;

/*
print_hierarchy () takes one argument, a filepath to a flux-accounting DB. It
will call load_accounting_db () to get a csv-style formatting. It will then
parse each line, fetching tokens delimited by ','. The formatting for lines
will be different if a line contains a bank or if it contains an association.
*/
std::string print_hierarchy (const std::string &filename)
{
    std::shared_ptr<weighted_tree_node_t> root;
    std::ostringstream out;
    std::stringstream buffer;
    std::string line, output;

    root = load_accounting_db (filename);
    weighted_walk_t walker (root);

    walker.dprint_csv (out);
    buffer << out.str();

    output.append ("Account|Username|RawShares|RawUsage\n");

    while (std::getline (buffer, line)) {
        std::string lvl, acct, username, shares, usage;
        std::stringstream ss (line);

        std::getline (ss, lvl, ',');
        std::getline (ss, acct, ',');
        std::getline (ss, username, ',');
        std::getline (ss, shares, ',');
        std::getline (ss, usage, ',');

        // determine indent based on level
        for (int i = 0; i < std::stoi (lvl); i++) {
            output.append (" ");
        }

        if (username == "%^+_nouser")
            output.append (acct + "||" + shares + '|' + usage);
        else
            output.append (acct + '|' + username + '|' + shares + '|' + usage);

        output.append ("\n");

    }

    return output;
}

int main (int argc, char** argv)
{
    // argument should be a filepath to a flux-accounting DB
    if (argc != 2) {
      std::cerr << "please specify one db file path" << std::endl;

      return (-1);
    }

    std::string output = print_hierarchy (argv[1]);
    std::cout << output << std::endl;

    return 0;
}
