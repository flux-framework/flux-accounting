/************************************************************\
 * Copyright 2025 Lawrence Livermore National Security, LLC
 * (c.f. AUTHORS, NOTICE.LLNS, COPYING)
 *
 * This file is part of the Flux resource manager framework.
 * For details, see https://github.com/flux-framework.
 *
 * SPDX-License-Identifier: LGPL-3.0
\************************************************************/

extern "C" {
#if HAVE_CONFIG_H
#include "config.h"
#endif
}

#include <iostream>
#include <fstream>
#include <vector>
#include <map>
#include <string>
#include <cmath>

#include "src/plugins/accounting.hpp"
#include "src/common/libtap/tap.h"

// define a test banks map
std::map<std::string, Bank> banks;


/*
 * initialize a map of Bank objects for testing
 */
void initialize_map (std::map<std::string, Bank> &banks)
{
    Bank A = { "A", 100 };
    Bank B = { "B", 200 };

    banks["A"] = A;
    banks["B"] = B;
}


/*
 * We can access a bank's properties by accessing the map by bank name.
 */
void test_bank_access_success ()
{
    Bank *A = &banks["A"];
    ok (A->name == "A", "Bank name can be accessed");
    ok ((fabs(A->priority - 100.0) < 1e-6), "Bank priority can be accessed");
}


/*
 * We can access a bank's priority by using the get_bank_priority () function
 * (since "priority" is of type double, we compare the value retrieved using an
 * epsilon value).
 */
void test_get_bank_priority_success ()
{
    double priority = get_bank_priority ("B", banks);

    ok ((fabs(priority - 200.0) < 1e-6), "Bank priority can be retrieved");
}


/*
 * If a bank cannot be found in the map, a priority of 0.0 is returned.
 */
void test_get_bank_priority_failure ()
{
    double priority = get_bank_priority ("foo", banks);

    ok ((fabs(priority - 0.0) < 1e-6),
        "A default priority of 0.0 will be returned when bank can't be found");
}


int main (int argc, char* argv[])
{
    initialize_map (banks);

    test_bank_access_success ();
    test_get_bank_priority_success ();
    test_get_bank_priority_failure ();

    // indicate we are done testing
    done_testing ();

    return EXIT_SUCCESS;
}

/*
 * vi:tabstop=4 shiftwidth=4 expandtab
 */
