/*
Copyright 2020 Lawrence Livermore National Security, LLC
(c.f. AUTHORS, NOTICE.LLNS, COPYING)

This file is part of the Flux resource manager framework.
For details, see https://github.com/flux-framework.

SPDX-License-Identifier: LGPL-3.0
*/
#include <iostream>
#include <sqlite3.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <tuple>

std::string hierarchy = "Bank|User|RawShares\n";

int get_sub_banks(
  sqlite3* DB,
  const std::string& bank_name,
  const std::string& indent,
  sqlite3_stmt *b_select_shares_stmt,
  sqlite3_stmt *b_select_sub_banks_stmt,
  sqlite3_stmt *b_select_associations_stmt
) {
  int exit = 0;

  // bind parameter to prepared SQL statement
  exit = sqlite3_bind_text(b_select_shares_stmt, 1, bank_name.c_str(), -1, NULL);
  if (exit != SQLITE_OK) {
      fprintf(stderr, "Failed to fetch data: %s\n", sqlite3_errmsg(DB));
      sqlite3_close(DB);

      return 1;
  }
  // execute SQL statement and store result
  exit = sqlite3_step(b_select_shares_stmt);
  std::string bank_shares = reinterpret_cast<char const*> (sqlite3_column_text(b_select_shares_stmt, 0));

  hierarchy.append(indent + bank_name + "||" + bank_shares + "\n");

  exit = sqlite3_bind_text(b_select_sub_banks_stmt, 1, bank_name.c_str(), -1, NULL);
  if (exit != SQLITE_OK) {
      fprintf(stderr, "Failed to fetch data: %s\n", sqlite3_errmsg(DB));
      sqlite3_close(DB);

      return 1;
  }
  exit = sqlite3_step(b_select_sub_banks_stmt);

  // vector of tuples to store usernames and their respective shares
  std::vector<std::tuple<std::string, std::string>> users;

  // vector of strings to hold sub banks
  std::vector<std::string> banks;

  // we've reached a bank with no sub banks, so print
  // out all associations under this sub bank
  if (exit != SQLITE_ROW) {
    exit = sqlite3_bind_text(b_select_associations_stmt, 1, bank_name.c_str(), -1, NULL);
    if (exit != SQLITE_OK) {
      fprintf(stderr, "Failed to fetch data: %s\n", sqlite3_errmsg(DB));
      sqlite3_close(DB);

      return 1;
    }

    // execute SQL statement
    exit = sqlite3_step(b_select_associations_stmt);
    while (exit == SQLITE_ROW) {
      std::string user = reinterpret_cast<char const*> (sqlite3_column_text(b_select_associations_stmt, 0));
      std::string single_user_shares = reinterpret_cast<char const*> (sqlite3_column_text(b_select_associations_stmt, 1));
      // place the user and their allocated shares into vector
      users.emplace_back(user, single_user_shares);
      exit = sqlite3_step(b_select_associations_stmt);
    }
    // iterate through associations and append them to the hierarchy string
    for (unsigned int i=0; i < users.size(); i++) {
      std::string username = std::get<0>(users[i]);
      std::string user_shares = std::get<1>(users[i]);
      hierarchy.append(indent + " " + bank_name + "|" + username + "|" + user_shares + "\n");
    }
  }
  // otherwise, this bank has sub banks, so call this helper
  // function again with the first sub bank it found
  else {
    while (exit == SQLITE_ROW) {
      // execute SQL statement
      std::string bank = reinterpret_cast<char const*> (sqlite3_column_text(b_select_sub_banks_stmt, 0));
      banks.push_back(bank);
      exit = sqlite3_step(b_select_sub_banks_stmt);
    }
    for (std::string b : banks) {
      // reset the prepared statements back to their initial state and
      // clear their bindings
      sqlite3_clear_bindings(b_select_associations_stmt);
      sqlite3_reset(b_select_associations_stmt);
      sqlite3_clear_bindings(b_select_sub_banks_stmt);
      sqlite3_reset(b_select_sub_banks_stmt);
      sqlite3_clear_bindings(b_select_shares_stmt);
      sqlite3_reset(b_select_shares_stmt);
      get_sub_banks(
        DB,
        b,
        indent + " ",
        b_select_shares_stmt,
        b_select_sub_banks_stmt,
        b_select_associations_stmt
      );
    }
  }

  return 0;
}


/*
print_hierarchy.cpp takes one argument, the path to a flux-accounting DB file.

It will look for a parent bank in the bank table. It will exit if it does not
find a root bank, or if it finds more than one root bank. Once it finds a root
bank, it will call get_sub_banks, which is a recursive function that traverses
the bank table with a depth-first search. Once it finds a bank with no sub
banks, it will print any associations and their corresponding shares under that
bank.
*/
int main(int argc, char** argv) {
  // SQL statements to retrieve data from flux-accounting database
  sqlite3_stmt *b_select_root_bank_stmt;
  sqlite3_stmt *b_select_shares_stmt;
  sqlite3_stmt *b_select_sub_banks_stmt;
  sqlite3_stmt *b_select_associations_stmt;

  std::string indent = "";

  // only one argument should be passed in; a filepath to the flux-accounting DB
  if (argc != 2) {
    std::cerr << "incorrect number of args passed; please specify one db file path" << std::endl;
    return(-1);
  }

  sqlite3* DB;
  int exit = 0;

  // open FluxAccounting database in read-write mode; if it does not exist yet,
  // create a new database file
  exit = sqlite3_open_v2(argv[1], &DB, SQLITE_OPEN_READWRITE, NULL);
  if (exit) {
    std::cerr << "error opening DB" << sqlite3_errmsg(DB) << std::endl;
    return 1;
  }

  // SELECT statement to get the shares of the current bank
  std::string select_shares_stmt = "SELECT bank_table.shares "
                      "FROM bank_table "
                      "WHERE bank=?";
  exit = sqlite3_prepare_v2(DB, select_shares_stmt.c_str(), -1, &b_select_shares_stmt, 0);

  // SELECT statement to get all sub banks of the current bank
  std::string select_sub_banks_stmt = "SELECT bank_table.bank "
                      "FROM bank_table "
                      "WHERE parent_bank=?";
  exit = sqlite3_prepare_v2(DB, select_sub_banks_stmt.c_str(), -1, &b_select_sub_banks_stmt, 0);

  // SELECT statement to get all associations from a bank
  std::string select_associations_stmt = "SELECT association_table.user_name, "
                      "association_table.shares, "
                      "association_table.bank "
                      " FROM association_table "
                      " WHERE association_table.bank=?";
  exit = sqlite3_prepare_v2(DB, select_associations_stmt.c_str(), -1, &b_select_associations_stmt, 0);

  // SELECT statement to get the root bank from the bank table
  std::string select_root_bank_stmt = "SELECT bank_table.bank "
                      "FROM bank_table "
                      "WHERE parent_bank=''";
  // compile SQL statement into byte code
  exit = sqlite3_prepare_v2(DB, select_root_bank_stmt.c_str(), -1, &b_select_root_bank_stmt, 0);
  if (exit != SQLITE_OK) {
      fprintf(stderr, "Failed to fetch data: %s\n", sqlite3_errmsg(DB));
      sqlite3_close(DB);

      return 1;
  }

  exit = sqlite3_step(b_select_root_bank_stmt);
  // store root bank name
  std::string root_bank;
  if (exit == SQLITE_ROW) {
      root_bank = reinterpret_cast<char const*> (sqlite3_column_text(b_select_root_bank_stmt, 0));
  }
  // otherwise, there is either no root bank or more than one
  // root bank; the program should exit
  else {
    std::cerr << "root bank not found, exiting" << std::endl;
    return 1;
  }

  // call recursive function
  get_sub_banks(
    DB,
    root_bank,
    indent,
    b_select_shares_stmt,
    b_select_sub_banks_stmt,
    b_select_associations_stmt
  );

  // destroy the prepared SQL statements
  sqlite3_finalize(b_select_root_bank_stmt);
  sqlite3_finalize(b_select_shares_stmt);
  sqlite3_finalize(b_select_sub_banks_stmt);
  sqlite3_finalize(b_select_associations_stmt);

  // print hierarchy
  std::cout << hierarchy << std::endl;

  // close DB connection
  sqlite3_close(DB);

}
