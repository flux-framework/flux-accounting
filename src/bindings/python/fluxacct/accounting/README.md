### Job Usage Factor Calculation Documentation

`calc_usage_factor()` is the function responsible for calculating a user's job usage factor as it relates to fairshare. The raw job usage factor is defined as the sum of products of number of nodes used (`nnodes`) and time elapsed (`t_elapsed`).

```
RawUsage = sum(nnodes * t_elapsed)
```

`create_db()` creates a new table **job_usage_factor_table** that is dynamically sized based on two options passed in when initially creating the database: **PriorityDecayHalfLife** and **PriorityUsageResetPeriod**. Each of these parameters represent a number of weeks by which to hold usage factors up to the time period where jobs no longer play a factor in calculating a usage factor. If these options aren't specified, the table defaults to 4 usage columns, each which represent one week's worth of jobs.

The **job_usage_factor_table** stores past job usage factors per user/bank combination in the `association_table`. When a user is first added to **association_table**, they are also added to to **job_usage_factor_table**.

```python
def calc_usage_factor(jobs_conn, acct_conn, user, bank, priority_decay_half_life=None, priority_usage_reset_period=None,)
```

The value of **PriorityDecayHalfLife** determines the amount of time that represents one "usage period" of jobs. It then uses `view_job_records()` to filter out the job archive and retrieve a user's jobs that have completed in the time period specified. It saves the last seen `t_inactive` timestamp in the `job_usage_factor_table` for the next query that it runs, which will look for jobs that have completed after the saved timestamp.

Past usage factors have a decay factor D (0.5) applied to them before they are added to the user's current usage factor.

```python
def apply_decay_factor(decay_factor, acct_conn, user=None, bank=None):
```

**usage_user_past** = `( D * Ulast_period) + (D * D * Uperiod-2) + ...`

After the current usage factor is calculated, it is written to the first usage bin in **job_usage_factor_table** along with the other, older factors. The oldest factor gets removed from the table since it is no longer needed.

---

### An example of calculating the job usage factor


Let's say a user has the following job records from the most recent **PriorityDecayHalfLife**:

```
   UserID Username  JobID         T_Submit            T_Run       T_Inactive  Nodes                                                                               R
0    1002     1002    102 1605633403.22141 1605635403.22141 1605637403.22141      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
1    1002     1002    103 1605633403.22206 1605635403.22206 1605637403.22206      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
2    1002     1002    104 1605633403.22285 1605635403.22286 1605637403.22286      2  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
3    1002     1002    105 1605633403.22347 1605635403.22348 1605637403.22348      1  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
4    1002     1002    106 1605633403.22416 1605635403.22416 1605637403.22416      1  {"version":1,"execution": {"R_lite":[{"rank":"0","children": {"core": "0"}}]}}
```

**total nodes used**:  8

**total time elapsed**:  10000.0

**usage_user_current**:

```
sum(nnodes * t_elapsed) = (2 * 2000) + (2 * 2000) + (2 * 2000) + (1 * 2000) + (1 * 2000)
                        = 4000 + 4000 + 4000 + 2000 + 2000
                        = 16000
```

And the user's past job usage factors (each one represents a **PriorityDecayHalfLife** period up to the **PriorityUsageResetPeriod**) consist of the following:

```
  username bank  usage_factor_period_0  usage_factor_period_1  usage_factor_period_2  usage_factor_period_3
0     1002    C               128.0000               64.00000               64.0000               16.00000
```

The past usage factors have the decay factor applied to them: `[64.0, 16.0, 8.0, 1.0]`

**usage_user_past**:  `64.0 + 16.0 + 8.0 + 1.0 = 89`

**usage_user_historical**: (usage\_user\_current) + (usage\_user\_past) = 16000 + 89 = 16089

---

### A typical workflow using calc_usage_factor() and update_end_half_life_period()

Ultimately, a Python script (through a `cron` job or the like) would end up utilizing both `calc_usage_factor()` and `update_end_half_life_period()` in the following manner.


Every **PriorityCalcPeriod**, the script would go through the following steps:

- A list of user/bank combinations would be fetched from the `association_table` in the flux-accounting database.

- For every user/bank combination, `calc_usage_factor()` is called; any new job records are fetched from the job-archive DB and a historical usage factor is generated. The appropriate values throughout the flux-accounting database would be updated to reflect this new usage factor.

- After the list of user/bank usage values are calculated, `update_end_half_life_period()` is called to determine if we are in a new half-life period. If we are, we update the flux-accounting database with the new timestamp that represents the end of the new half-life period.
