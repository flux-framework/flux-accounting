#!/usr/bin/env python3

###############################################################
# Copyright 2026 Lawrence Livermore National Security, LLC
# (c.f. AUTHORS, NOTICE.LLNS, COPYING)
#
# This file is part of the Flux resource manager framework.
# For details, see https://github.com/flux-framework.
#
# SPDX-License-Identifier: LGPL-3.0
###############################################################
"""Read and validate flux-accounting configuration.

flux-accounting follows the flux-core configuration conventions (see
flux-config(5)): configuration lives under an ``[accounting]`` TOML
table, subdivided by function into sections. Every key is optional;
built-in defaults match the values flux-accounting has always used when
creating a new database.
"""

from collections.abc import Mapping

import fluxacct.accounting
from fluxacct.accounting import util

# keys under [accounting.usage] that represent a duration; values may be
# expressed in Flux Standard Duration (e.g. "7d") or a number of seconds
DURATION_KEYS = (
    "reset-period",
    "decay-half-life",
)


def default_config():
    """
    Return the default flux-accounting configuration as a dictionary.
    These values match the hard-coded values historically used when
    creating the flux-accounting database.
    """
    return {
        "usage": {
            "reset-period": "28d",
            "decay-half-life": "7d",
            "decay-factor": 0.5,
            "calculation-mode": "periodic",
            "weights": {
                "node": 1.0,
                "core": 0.0,
                "gpu": 0.0,
            },
        },
        "priority": {
            "factors": {
                "fairshare": fluxacct.accounting.FSHARE_WEIGHT_DEFAULT,
                "queue": fluxacct.accounting.QUEUE_WEIGHT_DEFAULT,
                "bank": fluxacct.accounting.BANK_WEIGHT_DEFAULT,
                "urgency": fluxacct.accounting.URGENCY_WEIGHT_DEFAULT,
            },
        },
        "queues": {
            "deny-unknown": False,
        },
    }


class AccountingConfig(Mapping):
    """
    The flux-accounting configuration: built-in defaults, optionally
    customized by the [accounting] section of a TOML file.

    Behaves like a read-only dictionary of configuration sections (e.g.
    conf["usage"]["weights"], conf["priority"]["factors"]).
    """

    def __init__(self, path=None):
        """
        Initialize a configuration from built-in defaults, then apply any
        keys found in the [accounting] section of the TOML file at path.
        Durations are normalized to a number of seconds and the resulting
        configuration is validated.

        Args:
            path: optional path to a TOML configuration file.

        Raises:
            ValueError: the file cannot be parsed, is missing an
                [accounting] section, or contains an unknown key or an
                invalid value.
            OSError: the file cannot be opened.
        """
        self.path = path
        self._conf = default_config()
        if path is not None:
            self._merge_file(path)
        for key in DURATION_KEYS:
            self._conf["usage"][key] = util.parse_fsd(
                self._conf["usage"][key], key=f"usage.{key}"
            )
        self.validate()

    def _merge_file(self, path):
        """
        Overlay the [accounting] section of the TOML file at path onto
        the current configuration, rejecting unknown sections.
        """
        data = util.load_toml(path)
        if "accounting" not in data:
            raise ValueError(f"{path}: missing [accounting] section")
        for section, keys in data["accounting"].items():
            if section not in self._conf:
                raise ValueError(f"{path}: unknown section in [accounting]: {section}")
            if not isinstance(keys, dict):
                raise ValueError(f"{path}: [accounting.{section}] must be a table")
            self._merge_section(path, section, keys)

    def _merge_section(self, path, section, overrides):
        """
        Overlay the keys of one [accounting.<section>] table onto the
        section's defaults, rejecting unknown keys.
        """
        defaults = self._conf[section]
        for key, value in overrides.items():
            if key not in defaults:
                raise ValueError(
                    f"{path}: unknown key in [accounting.{section}]: {key}"
                )
            if isinstance(defaults[key], dict):
                if not isinstance(value, dict):
                    raise ValueError(
                        f"{path}: [accounting.{section}.{key}] must be a table"
                    )
                for subkey, subvalue in value.items():
                    if subkey not in defaults[key]:
                        raise ValueError(
                            f"{path}: unknown key in "
                            f"[accounting.{section}.{key}]: {subkey}"
                        )
                    defaults[key][subkey] = subvalue
            else:
                defaults[key] = value

    def validate(self):
        """
        Validate the types and ranges of the configuration values.

        Raises:
            ValueError: a key has a value of an invalid type or an
                out-of-range value.
        """
        usage = self._conf["usage"]
        if not 0.0 < usage["decay-factor"] < 1.0:
            raise ValueError(
                f"usage.decay-factor must be between 0.0 and 1.0, "
                f"but got {usage['decay-factor']}"
            )
        if usage["calculation-mode"] not in ("periodic", "continuous"):
            raise ValueError(
                f"usage.calculation-mode must be 'periodic' or 'continuous', "
                f"but got {usage['calculation-mode']}"
            )
        for rtype, weight in usage["weights"].items():
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(f"usage.weights.{rtype} must be a number")
        for factor, weight in self._conf["priority"]["factors"].items():
            if isinstance(weight, bool) or not isinstance(weight, int):
                raise ValueError(f"priority.factors.{factor} must be an integer")
        if not isinstance(self._conf["queues"]["deny-unknown"], bool):
            raise ValueError("queues.deny-unknown must be a boolean")

    def to_dict(self):
        """Return a deep copy of the configuration as a plain dictionary."""
        return {
            section: {
                key: dict(value) if isinstance(value, dict) else value
                for key, value in keys.items()
            }
            for section, keys in self._conf.items()
        }

    def __getitem__(self, key):
        """Return a configuration section by name."""
        return self._conf[key]

    def __iter__(self):
        """Iterate over configuration section names."""
        return iter(self._conf)

    def __len__(self):
        """Return the number of configuration sections."""
        return len(self._conf)

    def __repr__(self):
        """Return a debug representation including the source path."""
        return f"AccountingConfig(path={self.path!r}, {self._conf!r})"
