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
import fluxacct.accounting

from flux.constants import FLUX_MSGTYPE_REQUEST
from fluxacct.accounting import user_subcommands as u
from fluxacct.accounting import bank_subcommands as b
from fluxacct.accounting import job_archive_interface as jobs
from fluxacct.accounting import queue_subcommands as qu
from fluxacct.accounting import project_subcommands as p


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


def check_db_version(conn):
    # check version of database; if not up to date, output message
    # and exit
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    db_version = cur.fetchone()[0]
    if db_version < 20:
        print(
            "flux-accounting database out of date; please update DB with 'flux account-update-db' before running commands"
        )
        sys.exit(1)


# pylint: disable=broad-except
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

        endpoints = [
            "view_user",
            "add_user",
            "delete_user",
            "edit_user",
            "view_bank",
            "add_bank",
            "delete_bank",
            "edit_bank",
            "view_job_records",
            "update_usage",
            "add_queue",
            "view_queue",
            "delete_queue",
            "edit_queue",
            "add_project",
            "view_project",
            "delete_project",
            "shutdown_service",
        ]

        for name in endpoints:
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
            val = u.view_user(self.conn, msg.payload["username"])

            payload = {"view_user": val}

            # handle a flux-accounting.view_user request
            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in view-user: {val_err}")
        except sqlite3.OperationalError as sql_err:
            handle.respond_error(msg, 0, f"sqlite3.OperationalError: {sql_err}")
        except Exception as exc:
            # fall through to a non-OSError exception
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def add_user(self, handle, watcher, msg, arg):
        try:
            val = u.add_user(
                self.conn,
                msg.payload["username"],
                msg.payload["bank"],
                msg.payload["userid"],
                msg.payload["shares"],
                msg.payload["max_running_jobs"],
                msg.payload["max_active_jobs"],
                msg.payload["max_nodes"],
                msg.payload["queues"],
                msg.payload["projects"],
            )

            payload = {"add_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in add_user: {val_err}")
        except sqlite3.IntegrityError as integ_err:
            handle.respond_error(msg, 0, f"error in add_user: {integ_err}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def delete_user(self, handle, watcher, msg, arg):
        try:
            val = u.delete_user(self.conn, msg.payload["username"], msg.payload["bank"])

            payload = {"delete_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def edit_user(self, handle, watcher, msg, arg):
        try:
            val = u.edit_user(
                self.conn,
                msg.payload["username"],
                msg.payload["bank"],
                msg.payload["userid"],
                msg.payload["default_bank"],
                msg.payload["shares"],
                msg.payload["max_running_jobs"],
                msg.payload["max_active_jobs"],
                msg.payload["max_nodes"],
                msg.payload["queues"],
                msg.payload["projects"],
                msg.payload["default_project"],
            )

            payload = {"edit_user": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in edit_user: {val_err}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def view_bank(self, handle, watcher, msg, arg):
        try:
            val = b.view_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload["tree"],
                msg.payload["users"],
            )

            payload = {"view_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in view-bank: {val_err}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def add_bank(self, handle, watcher, msg, arg):
        try:
            val = b.add_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload["shares"],
                msg.payload["parent_bank"],
            )

            payload = {"add_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def delete_bank(self, handle, watcher, msg, arg):
        try:
            val = b.delete_bank(self.conn, msg.payload["bank"])

            payload = {"delete_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def edit_bank(self, handle, watcher, msg, arg):
        try:
            val = b.edit_bank(
                self.conn,
                msg.payload["bank"],
                msg.payload["shares"],
                msg.payload["parent_bank"],
            )

            payload = {"edit_bank": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    # pylint: disable=no-self-use
    def view_job_records(self, handle, watcher, msg, arg):
        try:
            # connect to job-archive DB
            jobs_conn = establish_sqlite_connection(msg.payload["path"])

            val = jobs.output_job_records(
                jobs_conn,
                msg.payload["output_file"],
                jobid=msg.payload["jobid"],
                user=msg.payload["user"],
                before_end_time=msg.payload["before_end_time"],
                after_start_time=msg.payload["after_start_time"],
            )

            payload = {"view_job_records": val}

            jobs_conn.close()
            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def update_usage(self, handle, watcher, msg, arg):
        try:
            jobs_conn = establish_sqlite_connection(msg.payload["job_archive_db_path"])

            val = jobs.update_job_usage(
                self.conn,
                jobs_conn,
                msg.payload["priority_decay_half_life"],
            )

            payload = {"update_job_usage": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def add_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.add_queue(
                self.conn,
                msg.payload["queue"],
                msg.payload["min_nodes_per_job"],
                msg.payload["max_nodes_per_job"],
                msg.payload["max_time_per_job"],
                msg.payload["priority"],
            )

            payload = {"add_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def view_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.view_queue(self.conn, msg.payload["queue"])

            payload = {"view_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in view-queue: {val_err}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def delete_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.delete_queue(self.conn, msg.payload["queue"])

            payload = {"delete_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def edit_queue(self, handle, watcher, msg, arg):
        try:
            val = qu.edit_queue(
                self.conn,
                msg.payload["queue"],
                msg.payload["min_nodes_per_job"],
                msg.payload["max_nodes_per_job"],
                msg.payload["max_time_per_job"],
                msg.payload["priority"],
            )

            payload = {"edit_queue": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def add_project(self, handle, watcher, msg, arg):
        try:
            val = p.add_project(self.conn, msg.payload["project"])

            payload = {"add_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def view_project(self, handle, watcher, msg, arg):
        try:
            val = p.view_project(self.conn, msg.payload["project"])

            payload = {"view_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except ValueError as val_err:
            handle.respond_error(msg, 0, f"error in view-project: {val_err}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )

    def delete_project(self, handle, watcher, msg, arg):
        try:
            val = p.delete_project(self.conn, msg.payload["project"])

            payload = {"delete_project": val}

            handle.respond(msg, payload)
        except KeyError as exc:
            handle.respond_error(msg, 0, f"missing key in payload: {exc}")
        except Exception as exc:
            handle.respond_error(
                msg, 0, f"a non-OSError exception was caught: {str(exc)}"
            )


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
    db_path = args.path if args.path else fluxacct.accounting.db_path
    conn = establish_sqlite_connection(db_path)

    # check version of database; if not up to date, output message
    # and exit
    cur = conn.cursor()
    cur.execute("PRAGMA user_version")
    db_version = cur.fetchone()[0]
    if db_version < 20:
        LOGGER.error(
            "flux-accounting database out of date; please update DB with 'flux account-update-db' before running commands"
        )
        sys.exit(1)

    handle = flux.Flux()
    server = AccountingService(handle, conn)

    if args.background:
        background()

    handle.reactor_run()


if __name__ == "__main__":
    main()
