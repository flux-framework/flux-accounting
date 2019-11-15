_NOTE: The interfaces of flux-accounting are being actively developed and are not yet stable. The Github issue tracker is the primary way to communicate with the developers._

## flux-accounting

Development for a bank/accounting interface for the Flux resource manager. Writes and saves job step history, user account information, and priority calculation to persistent storage using Python's SQLite3 API. 

##### job step history

Running as a cron job, `write_jobs.py` uses a flux-core RPC to retrieve job data that have recently transitioned to an INACTIVE state in the past _x_ minutes. It parses the job record data and writes it to a SQLite database, which can be queried at a later time. 

##### user account information

Users have banks that they can charge their jobs against; this will affect their priority when submitting future jobs in order to maintain a fair balance of resources between users running jobs on a single cluster. Multiple factors play a role in determining a user's job priority, but in general, the amount of resources used vs. the resource limits initially allocated will either lower or heighten a user's job priority. 

Priority will be calculated by calling another Python file, `fairshare.py`, which will retrieve user account information amd job record history and perform a "fairshare" calculation to determine a user's job priority on a cluster. 
