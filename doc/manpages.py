###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################

author = "This page is maintained by the Flux community."

# Add man page entries with the following information:
# - Relative file path (without .rst extension)
# - Man page name
# - Man page description
# - Author (use [author])
# - Manual section
man_pages = [
    (
        "man1/flux-account",
        "flux-account",
        "flux-accounting commands",
        [author],
        1,
    ),
    (
        "man1/flux-account-create-db",
        "flux-account-create-db",
        "create the flux-accounting SQLite database",
        [author],
        1,
    ),
    (
        "man1/flux-account-pop-db",
        "flux-account-pop-db",
        "populate a flux-accounting database with .csv files",
        [author],
        1,
    ),
    (
        "man1/flux-account-export-db",
        "flux-account-export-db",
        "export flux-accounting database information into .csv files",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-user",
        "flux-account-view-user",
        "view information about a user in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-add-user",
        "flux-account-add-user",
        "add an association to the association_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-delete-user",
        "flux-account-delete-user",
        "deactivate an association in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-edit-user",
        "flux-account-edit-user",
        "modify an attribute for an association in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-bank",
        "flux-account-view-bank",
        "view information about a bank in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-add-bank",
        "flux-account-add-bank",
        "add a bank to the bank_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-delete-bank",
        "flux-account-delete-bank",
        "deactivate a bank in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-edit-bank",
        "flux-account-edit-bank",
        "modify an attribute for a bank in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-list-banks",
        "flux-account-list-banks",
        "list all banks in bank_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-queue",
        "flux-account-view-queue",
        "view information about a queue in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-add-queue",
        "flux-account-add-queue",
        "add a queue to the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-delete-queue",
        "flux-account-delete-queue",
        "delete a queue from the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-edit-queue",
        "flux-account-edit-queue",
        "edit a queue's properties in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-list-queues",
        "flux-account-list-queues",
        "list all defined queues in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-list-users",
        "flux-account-list-users",
        "list all associations in the association_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-add-project",
        "flux-account-add-project",
        "add a project to the project_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-project",
        "flux-account-view-project",
        "view information about a project in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-delete-project",
        "flux-account-delete-project",
        "delete a project from the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-list-projects",
        "flux-account-list-projects",
        "list all projects in the project_table",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-factor",
        "flux-account-view-factor",
        "view the configured integer weight for a given priority factor",
        [author],
        1,
    ),
    (
        "man1/flux-account-edit-factor",
        "flux-account-edit-factor",
        "edit the configured integer weight for a given priority factor",
        [author],
        1,
    ),
    (
        "man1/flux-account-list-factors",
        "flux-account-list-factors",
        "list all of the priority factors and their weights",
        [author],
        1,
    ),
    (
        "man1/flux-account-reset-factors",
        "flux-account-reset-factors",
        "reset all of the priority factors to their default weights",
        [author],
        1,
    ),
    (
        "man1/flux-account-jobs",
        "flux-account-jobs",
        "view a breakdown of an association's job priorities",
        [author],
        1,
    ),
    (
        "man1/flux-account-view-job-records",
        "flux-account-view-job-records",
        "view job records in the flux-accounting database",
        [author],
        1,
    ),
    (
        "man1/flux-account-show-usage",
        "flux-account-show-usage",
        "display a chart of the top associations or banks in terms of job usage",
        [author],
        1,
    ),
]
