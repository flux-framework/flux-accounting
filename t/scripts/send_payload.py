#!/usr/bin/env python3

import sys
import json
import flux

h = flux.Flux()

with open(sys.argv[1]) as data_file:
    data = json.load(data_file)

for user in data["users"]:
    h.rpc("job-manager.mf_priority.rec_update", user).get()
