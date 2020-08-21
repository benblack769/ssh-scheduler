Design: Host over TCP, port 51241

Controller daemon:
  * machines config
  * Should be robust to worker crashes/restarts

Worker daemon:
  * Controller daemon IP
  * Should be robust to controller crashes/restarts

Client (on controller process):
  * ssh login to data folders
  * run command locally to start job
  * kill job
  * view job stdout/stderr (kept up to date regularly)
  * view job machine ID
  * view job list

Job starting:
  * Travis-like yaml file with global/local options
    * Batch ID
    * Job ID (allow array notation, stores index in bash variable JOB_ID)
    * Job resources
      * exclusive (optional, default False)
      * machine ID (optional, default None)
      * n-CPU
      * CPU-mem
      * Exclusive GPU (default True)
      * GPU-mem (needed if exclusive GPU is not True)
      * Timeout (optional, kill when times out, default infinite time)
    * Job priority (default 0)
    * Install script (does not give sudo access)
    * Run script (does not give sudo access)
    * Folder(s) to copy forward
    * Folder(s) to copy backwards

Job viewing:
  * View job stdout/stderr/fetchable files by job ID (gets up to date files)
  * View job allocated machine ID for active job
  * Get job summary status for batch by batch ID or for all batches
    * print in queue order
    * Active/inactive
    * machine ID for active jobs (optional)
    *
  * Get job summary status for
  * Get active job summary for specific machine

Job management:
  * Kill job
  * Kill batch
  * Change job/batch priority (warns if job is active already, but still changes priority)
  * Stop jobs on specific machine and disconnect machine (and put them back on the queue with +1 priority)

Worker viewing:
  * Get machine status (responsive/unresponsive)
