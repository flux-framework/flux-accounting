#!/usr/bin/env python3

import sys
import json
import flux

h = flux.Flux()

with open(sys.argv[1]) as data_file:
    bulk_update_data = json.load(data_file)

h.rpc("job-manager.mf_priority.rec_update", json.dumps(bulk_update_data)).get()
