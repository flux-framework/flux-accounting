###############################################################
# Copyright 2022 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
import signal
import sys
import sqlite3
import os
import argparse
import logging

import flux
import flux.constants
import fluxacct.accounting

from flux.constants import FLUX_MSGTYPE_REQUEST
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import job_usage_calculation as jobs
from fluxacct.accounting import queue_subcommands as qu
from fluxacct.accounting import project_subcommands as p
from fluxacct.accounting import jobs_table_subcommands as j
from fluxacct.accounting import db_info_subcommands as d
from fluxacct.accounting import priorities as prio
from fluxacct.accounting import visuals as vis
from fluxacct.accounting import sql_util as sql


def establish_sqlite_connection(path):
    # try to open database file; will exit with -1 if database file not found
    if not os.path.isfile(path):
        print(f"Database file does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    db_uri = "file:" + path + "?mode=rw"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
        # set foreign keys constraint
        conn.execute("PRAGMA foreign_keys = 1")
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as exc:
        print(f"Unable to open database file: {db_uri}", file=sys.stderr)
        print(f"Exception: {exc}")
        sys.exit(1)

    return conn


def background():
    pid = os.fork()
    if pid > 0:
        # exit first parent
        sys.exit(0)


# pylint: disable=broad-except, too-many-public-methods
class AccountingService:
    def __init__(self, flux_handle, conn):

        self.handle = flux_handle
        self.conn = conn

        try:
            # register service with broker
            self.handle.service_register("accounting").get()
            print("registered accounting service", file=sys.stderr)
        except FileExistsError:
            LOGGER.error("flux-accounting service is already registered")

        # register signal watcher for SIGTERM to initiate shutdown
        self.handle.signal_watcher_create(signal.SIGTERM, self.shutdown).start()
        self.handle.signal_watcher_create(signal.SIGINT, self.shutdown).start()

        general_endpoints = [
            "view_user",
            "view_bank",
            "list_banks",
            "view_job_records",
            "view_queue",
            "view_project",
            "list_projects",
            "list_queues",
            "list_users",
            "view_factor",
            "list_factors",
            "jobs",
            "show_usage",
        ]

        privileged_endpoints = [
            "add_user",
            "delete_user",
            "edit_user",
            "add_bank",
            "delete_bank",
            "edit_bank",
            "add_queue",
            "delete_queue",
            "edit_queue",
            "add_project",
            "delete_project",
            "scrub_old_jobs",
            "export_db",
            "pop_db",
            "shutdown_service",
            "edit_factor",
            "reset_factors",
            "edit_all_users",
            "sync_userids",
            "export_json",
        ]

        for name in general_endpoints:
            watcher = self.handle.msg_watcher_create(
                getattr(self, name), FLUX_MSGTYPE_REQUEST, f"accounting.{name}", self
            )
            self.handle.msg_handler_allow_rolemask(
                watcher.handle, flux.constants.FLUX_ROLE_USER
            )
            watcher.start()

        for name in privileged_endpoints:
            self.handle.msg_watcher_create(
                getattr(self, name), FLUX_MSGTYPE_REQUEST, f"accounting.{name}", self
            ).start()

    def shutdown(self, handle, watcher, signum, arg):
        print("Shutting down...", file=sys.stderr)
        self.conn.close()
        self.handle.service_unregister("accounting").get()
        self.handle.reactor_stop()

    # watches for a shutdown message
    def shutdown_service(self, handle, watcher, msg, arg):
        print("Shutting down...", file=sys.stderr)
        self.conn.close()
        self.handle.service_unregister("accounting").get()
        self.handle.reactor_stop()
        handle.respond(msg)

    def view_user(self, handle, watcher, msg, arg):
        try:
            # call view-user function
            val = u.view_user(
                self.conn,
                msg.payload["username"],
                msg.payload.get("parsable"),
                msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                msg.payload.get("list_banks"),
                msg.payload.get("format"),
                msg.payload.get("job_usage"),
            )

            payload = {"view_user": val}

            # handle a flux-accounting.view_user request
            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"view-user: missing key in payload: {exc}")
        # SQLite errors and exceptions raised are related to the DB's operation and are
        # not necessarily under the control of the programmer, e.g. the DB path cannot
        # be found or transaction could not be processed
        # (https://docs.python.org/3/library/sqlite3.html#sqlite3.OperationalError)
        except Exception as exc:
            handle.respond_error(msg, 0, f"view-user: {type(exc).__name__}: {exc}")

    # pylint: disable=no-self-use
    def list_users(self, handle, watcher, msg, arg):
        try:
            val = u.list_users(
                self.conn,
                cols=msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                json_fmt=msg.payload.get("json"),
                format_string=msg.payload.get("format"),
                active=msg.payload.get("active"),
                bank=msg.payload.get("bank"),
                shares=msg.payload.get("shares"),
                max_running_jobs=msg.payload.get("max_running_jobs"),
                max_active_jobs=msg.payload.get("max_active_jobs"),
                max_nodes=msg.payload.get("max_nodes"),
                max_cores=msg.payload.get("max_cores"),
                queues=msg.payload.get("queues"),
                projects=msg.payload.get("projects"),
                default_project=msg.payload.get("default_project"),
            )

            payload = {"list_users": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"list-users: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"list-users: {type(exc).__name__}: {exc}")

    def add_user(self, handle, watcher, msg, arg):
        try:
            val = u.add_user(
                conn=self.conn,
                username=msg.payload["username"],
                bank=msg.payload["bank"],
                uid=msg.payload.get("userid"),
                shares=msg.payload.get("shares"),
                fairshare=msg.payload.get("fairshare"),
                max_running_jobs=msg.payload.get("max_running_jobs"),
                max_active_jobs=msg.payload.get("max_active_jobs"),
                max_nodes=msg.payload.get("max_nodes"),
                max_cores=msg.payload.get("max_cores"),
                queues=msg.payload.get("queues"),
                projects=msg.payload.get("projects"),
                default_project=msg.payload.get("default_project"),
            )

            payload = {"add_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"add-user: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"add-user: {type(exc).__name__}: {exc}")

    def delete_user(self, handle, watcher, msg, arg):
        try:
            val = u.delete_user(
                self.conn,
                msg.payload["username"],
                msg.payload["bank"],
                msg.payload.get("force"),
            )

            payload = {"delete_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"delete-user: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"delete-user: {type(exc).__name__}: {exc}")

    def edit_user(self, handle, watcher, msg, arg):
        try:
            val = u.edit_user(
                conn=self.conn,
                username=msg.payload["username"],
                bank=msg.payload.get("bank"),
                userid=msg.payload.get("userid"),
                default_bank=msg.payload.get("default_bank"),
                shares=msg.payload.get("shares"),
                fairshare=msg.payload.get("fairshare"),
                max_running_jobs=msg.payload.get("max_running_jobs"),
                max_active_jobs=msg.payload.get("max_active_jobs"),
                max_nodes=msg.payload.get("max_nodes"),
                max_cores=msg.payload.get("max_cores"),
                queues=msg.payload.get("queues"),
                projects=msg.payload.get("projects"),
                default_project=msg.payload.get("default_project"),
            )

            payload = {"edit_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"edit-user: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"edit-user: {type(exc).__name__}: {exc}")

    def view_bank(self, handle, watcher, msg, arg):
        try:
            val = b.view_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload.get("tree"),
                msg.payload.get("users"),
                msg.payload.get("parsable"),
                msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                msg.payload.get("format"),
                msg.payload.get("concise"),
            )

            payload = {"view_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"view-bank: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"view-bank: {type(exc).__name__}: {exc}")

    def add_bank(self, handle, watcher, msg, arg):
        try:
            val = b.add_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload["shares"],
                msg.payload.get("parent_bank"),
                msg.payload.get("priority"),
            )

            payload = {"add_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"add-bank: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"add-bank: {type(exc).__name__}: {exc}")

    def delete_bank(self, handle, watcher, msg, arg):
        try:
            val = b.delete_bank(
                self.conn, msg.payload["bank"], msg.payload.get("force")
            )

            payload = {"delete_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"delete-bank: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"delete-bank: {type(exc).__name__}: {exc}")

    def edit_bank(self, handle, watcher, msg, arg):
        try:
            val = b.edit_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload.get("shares"),
                msg.payload.get("parent_bank"),
                msg.payload.get("priority"),
            )

            payload = {"edit_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"edit-bank: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"edit-bank: {type(exc).__name__}: {exc}")

    def list_banks(self, handle, watcher, msg, arg):
        try:
            val = b.list_banks(
                self.conn,
                msg.payload.get("inactive"),
                msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                msg.payload.get("json"),
                msg.payload.get("format"),
            )

            payload = {"list_banks": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"list-banks: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"list-banks: {type(exc).__name__}: {exc}")

    # pylint: disable=no-self-use
    def view_job_records(self, handle, watcher, msg, arg):
        try:
            val = j.view_jobs(
                self.conn,
                msg.payload.get("format"),
                jobid=msg.payload.get("jobid"),
                user=msg.payload.get("user"),
                before_end_time=msg.payload.get("before_end_time"),
                after_start_time=msg.payload.get("after_start_time"),
                project=msg.payload.get("project"),
                bank=msg.payload.get("bank"),
                requested_duration=msg.payload.get("requested_duration"),
                actual_duration=msg.payload.get("actual_duration"),
                duration_delta=msg.payload.get("duration_delta"),
            )

            payload = {"view_job_records": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"view-job-records: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"view-job-records: {type(exc).__name__}: {exc}"
            )

    def add_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.add_queue(
                self.conn,
                msg.payload["queue"],
                msg.payload.get("min_nodes_per_job"),
                msg.payload.get("max_nodes_per_job"),
                msg.payload.get("max_time_per_job"),
                msg.payload.get("priority"),
                msg.payload.get("max_running_jobs"),
                msg.payload.get("max_nodes_per_assoc"),
            )

            payload = {"add_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"add-queue: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"add-queue: {type(exc).__name__}: {exc}")

    def view_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.view_queue(
                self.conn,
                msg.payload["queue"],
                msg.payload.get("parsable"),
                msg.payload.get("format"),
            )

            payload = {"view_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"view-queue: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"view-queue: {type(exc).__name__}: {exc}")

    def delete_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.delete_queue(self.conn, msg.payload["queue"])

            payload = {"delete_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"delete-queue: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"delete-queue: {type(exc).__name__}: {exc}")

    def edit_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.edit_queue(
                self.conn,
                msg.payload["queue"],
                msg.payload.get("min_nodes_per_job"),
                msg.payload.get("max_nodes_per_job"),
                msg.payload.get("max_time_per_job"),
                msg.payload.get("priority"),
                msg.payload.get("max_running_jobs"),
                msg.payload.get("max_nodes_per_assoc"),
            )

            payload = {"edit_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"edit-queue: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"edit-queue: {type(exc).__name__}: {exc}")

    def add_project(self, handle, watcher, msg, arg):
        try:
            val = p.add_project(self.conn, msg.payload["project"])

            payload = {"add_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"add-project: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"add-project: {type(exc).__name__}: {exc}")

    def view_project(self, handle, watcher, msg, arg):
        try:
            val = p.view_project(
                self.conn,
                msg.payload["project"],
                msg.payload.get("parsable"),
                msg.payload.get("format"),
            )

            payload = {"view_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"view-project: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"view-project: {type(exc).__name__}: {exc}")

    def delete_project(self, handle, watcher, msg, arg):
        try:
            val = p.delete_project(self.conn, msg.payload["project"])

            payload = {"delete_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"delete-project: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(msg, 0, f"delete-project: {type(exc).__name__}: {exc}")

    def list_projects(self, handle, watcher, msg, arg):
        try:
            val = p.list_projects(
                self.conn,
                msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                msg.payload.get("json"),
                msg.payload.get("format"),
            )

            payload = {"list_projects": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"list-projects: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(msg, 0, f"list-projects: {type(exc).__name__}: {exc}")

    def scrub_old_jobs(self, handle, watcher, msg, arg):
        try:
            val = jobs.scrub_old_jobs(self.conn, msg.payload["num_weeks"])

            payload = {"scrub_old_jobs": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"scrub-old-jobs: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(msg, 0, f"scrub-old-jobs: {type(exc).__name__}: {exc}")

    def export_db(self, handle, watcher, msg, arg):
        try:
            val = d.export_db_info(
                self.conn,
                msg.payload.get("users"),
                msg.payload.get("banks"),
            )

            payload = {"export_db": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"export-db: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"export-db: {type(exc).__name__}: {exc}")

    def pop_db(self, handle, watcher, msg, arg):
        try:
            val = d.populate_db(
                self.conn,
                msg.payload.get("users"),
                msg.payload.get("banks"),
            )

            payload = {"pop_db": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"pop-db: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"pop-db: {type(exc).__name__}: {exc}")

    def list_queues(self, handle, watcher, msg, arg):
        try:
            val = qu.list_queues(
                self.conn,
                msg.payload.get("fields").split(",")
                if msg.payload.get("fields")
                else None,
                msg.payload.get("json"),
                msg.payload.get("format"),
            )

            payload = {"list_queues": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"list-queues: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"list-queues: {type(exc).__name__}: {exc}")

    def view_factor(self, handle, watcher, msg, arg):
        try:
            val = prio.view_factor(
                conn=self.conn,
                factor=msg.payload["factor"],
                json_fmt=msg.payload.get("json"),
                format_string=msg.payload.get("format"),
            )

            payload = {"view_factor": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"view-factor: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"view-factor: {type(exc).__name__}: {exc}")

    def edit_factor(self, handle, watcher, msg, arg):
        try:
            val = prio.edit_factor(
                conn=self.conn,
                factor=msg.payload["factor"],
                weight=msg.payload["weight"],
            )

            payload = {"edit_factor": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"edit-factor: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"edit-factor: {type(exc).__name__}: {exc}")

    def list_factors(self, handle, watcher, msg, arg):
        try:
            val = prio.list_factors(
                conn=self.conn,
                cols=msg.payload["fields"].split(",")
                if msg.payload.get("fields")
                else None,
                json_fmt=msg.payload.get("json"),
                format_string=msg.payload.get("format"),
            )

            payload = {"list_factors": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"list-factors: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"list-factors: {type(exc).__name__}: {exc}")

    def reset_factors(self, handle, watcher, msg, arg):
        try:
            val = prio.reset_factors(self.conn)

            payload = {"reset_factors": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"reset-factors: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(msg, 0, f"reset-factors: {type(exc).__name__}: {exc}")

    def jobs(self, handle, watcher, msg, arg):
        try:
            val = prio.job_priorities(
                conn=self.conn,
                username=msg.payload["username"],
                bank=msg.payload.get("bank"),
                queue=msg.payload.get("queue"),
                format_string=msg.payload.get("format"),
                filters=msg.payload.get("filter"),
                max_entries=msg.payload.get("count"),
                since=msg.payload.get("since"),
                jobids=msg.payload.get("jobids"),
                verbose=msg.payload.get("verbose"),
            )

            payload = {"jobs": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"jobs: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"jobs: {type(exc).__name__}: {exc}")

    def show_usage(self, handle, watcher, msg, arg):
        try:
            val = vis.show_usage(
                conn=self.conn,
                table=msg.payload["table"],
                limit=msg.payload.get("limit"),
            )

            payload = {"show_usage": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"show-usage: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"show-usage: {type(exc).__name__}: {exc}")

    def edit_all_users(self, handle, watcher, msg, arg):
        try:
            val = u.edit_all_users(
                conn=self.conn,
                bank=msg.payload.get("bank"),
                default_bank=msg.payload.get("default_bank"),
                shares=msg.payload.get("shares"),
                fairshare=msg.payload.get("fairshare"),
                max_running_jobs=msg.payload.get("max_running_jobs"),
                max_active_jobs=msg.payload.get("max_active_jobs"),
                max_nodes=msg.payload.get("max_nodes"),
                max_cores=msg.payload.get("max_cores"),
                queues=msg.payload.get("queues"),
                projects=msg.payload.get("projects"),
                default_project=msg.payload.get("default_project"),
            )

            payload = {"edit_all_users": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(
                msg, 0, f"edit-all-users: missing key in payload: {exc}"
            )
        except Exception as exc:
            handle.respond_error(msg, 0, f"edit-all-users: {type(exc).__name__}: {exc}")

    def sync_userids(self, handle, watcher, msg, arg):
        try:
            val = u.sync_userids(conn=self.conn)

            payload = {"sync_userids": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"sync-userids: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"sync-userids: {type(exc).__name__}: {exc}")

    def export_json(self, handle, watcher, msg, arg):
        try:
            val = d.export_as_json(conn=self.conn)

            payload = {"export_json": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"export-json: missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(msg, 0, f"export-json: {type(exc).__name__}: {exc}")


LOGGER = logging.getLogger("flux-uri")


@flux.util.CLIMain(LOGGER)
def main():
    parser = argparse.ArgumentParser(prog="flux-uri")
    parser.add_argument(
        "-p", "--path", dest="path", help="specify location of database file"
    )
    parser.add_argument(
        "-t",
        "--test-background",
        action="store_true",
        dest="background",
        help="used for testing",
    )
    args = parser.parse_args()

    # try to connect to flux-accounting database; if connection fails, exit
    # flux-accounting service
    db_path = args.path if args.path else fluxacct.accounting.DB_PATH
    conn = establish_sqlite_connection(db_path)

    # check version of database; if not up to date, output message and exit
    if sql.db_version(conn) < fluxacct.accounting.DB_SCHEMA_VERSION:
        LOGGER.error(
            "flux-accounting database out of date; please update DB with "
            "'flux account-update-db' before running commands"
        )
        sys.exit(1)

    handle = flux.Flux()
    server = AccountingService(handle, conn)

    if args.background:
        background()

    handle.reactor_run()


if __name__ == "__main__":
    main()
