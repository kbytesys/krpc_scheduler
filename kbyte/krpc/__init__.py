__author__ = 'Andrea'

import krpc.client
import krpc.service
from threading import Thread, RLock
import time
import logging

class KRPCVesselTelemetry():
    def __init__(self, conn, vessel):
        # Base telemetry
        self.conn = conn
        self.space_center = conn.space_center
        self.vessel = vessel
        self.ut = conn.add_stream(getattr, conn.space_center, 'ut')
        self.altitude = conn.add_stream(getattr, vessel.flight(), 'mean_altitude')
        self.stage = conn.add_stream(getattr, vessel.control, 'current_stage')
        self.vessel_orbit_speed = conn.add_stream(getattr, vessel.flight(vessel.orbit.body.reference_frame), 'speed')

    def add_vessel_flight_telemetry(self, attrib_name, proto_name):
        setattr(self, attrib_name, self.conn.add_stream(getattr, self.vessel.flight(), proto_name))

    """
    def vessel_orbit_speed(self):
        return self.vessel.flight(self.vessel.orbit.body.reference_frame).speed
    """

class KRPCJob():
    def __init__(self, jobid, priority=10, stage=None):
        self.priority = priority
        self.stage = stage
        self.jobid = jobid
        self.disabled = False
        self.expired = False

    def execute(self, telemetry, scheduler, stage, cycle_commands: set):
        pass

    def execute_exit_stage(self, telemetry, scheduler, stage, cycle_commands: set):
        pass

    def execute_enter_stage(self, telemetry, scheduler, stage, cycle_commands: set):
        pass

    def execute_custom_command(self, telemetry, scheduler, stage, command):
        pass


# noinspection PyUnresolvedReferences
"""
Scheduler class, you can perform scheduler jobs with a configurable frequency
"""
class KRPCVesselScheduler(Thread):
    def __init__(self, conn: krpc.client.Client, telemetry: KRPCVesselTelemetry=None, frequency=0.5):
        Thread.__init__(self)
        self.conn = conn
        self.telemetry = telemetry
        self.space_center = conn.space_center
        self.vessel = conn.space_center.active_vessel
        self.frequency = frequency
        self.joblist = list()
        self.queuelock = RLock()
        self.shutdown = True

        if telemetry is None:
            self.telemetry = KRPCVesselTelemetry(self.conn, self.vessel)

    """
    Register a job in the scheduler
    """
    def register_job(self, job: KRPCJob):
        self.queuelock.acquire()
        self.joblist.append(job)
        self.joblist.sort(key=lambda x: x.priority, reverse=True)
        self.queuelock.release()

    """
    Remove a job from the scheduler by jobid
    """
    def unregister_job(self, jobid):
        self.queuelock.acquire()
        for job in self.joblist:
            if job.jobid == jobid:
                self.joblist.remove(job)
                break
        self.queuelock.release()

    """
    Remove a job from the scheduler by job object
    """
    def unregister_job_object(self, job: KRPCJob):
        self.queuelock.acquire()
        try:
            self.joblist.remove(job)
        except ValueError:
            pass
        self.queuelock.release()

    """
    Run the scheduler. In every cycle the scheduler manege the job list cleanup from expired items, manage stage changes,
    execute allowed jobs by status and current stage and perform end cycle commands requested by jobs. Please check the
    KRPCJob doc for better infos.
    """
    def run(self):
        self.shutdown = False
        scheduler_stage = self.telemetry.stage()
        while not self.shutdown:
            self.queuelock.acquire()
            '''
            We want to assure list coherence and thread safe ops. First we clone the jobs list and perform some stage
            related ops. This cycle also purge expired elements.
            '''
            cloned_jobs = list()
            toremove = list()
            for job in self.joblist:
                if job.expired:
                    toremove.append(job)

                if not job.disabled and not job.expired and (job.stage is None or job.stage == scheduler_stage):
                    cloned_jobs.append(job)
                    logging.debug("Job %s allowed in this scheduler cycle" % job.jobid)

            for job in toremove:
                self.unregister_job_object(job)
                logging.debug("Job %s removed from scheduler." % job.jobid)

            self.queuelock.release()

            '''
            Check the current stage, if the scheduler stage is minor of telemetry stage, we have switched vessel or
            reverted the flight. Abort the scheduler to avoid an atomic fallout.
            '''
            if scheduler_stage < self.telemetry.stage():
                logging.error("Scheduler stage not coerent!!! Vechile switch???")
                cycle_commands = ('shutdown',)

            else:

                cycle_commands = set()

                '''
                React to stage changes, execute job's exit and enter events until the right stage is reached.
                '''
                if scheduler_stage != self.telemetry.stage():
                    while scheduler_stage != self.telemetry.stage():
                        logging.info("Change stage from %d to %d" % (scheduler_stage, self.telemetry.stage()))
                        for job in cloned_jobs:
                            try:
                                job.execute_exit_stage(self.telemetry, self, scheduler_stage, cycle_commands)
                            except Exception as e:
                                logging.error("Job Exit Stage error: jobid %s stage %s error %s" %
                                              (job.jobid, scheduler_stage, e))
                        scheduler_stage -= 1
                        for job in cloned_jobs:
                            try:
                                job.execute_enter_stage(self.telemetry, self, scheduler_stage, cycle_commands)
                            except Exception as e:
                                logging.error("Job Enter Stage error: jobid %s stage %s error %s" %
                                              (job.jobid, scheduler_stage, e))

                '''
                Main scheduler duty. Every job is executed from the priority queue. Every job can add elements to
                cycle_commands set. Atm the scheduler handle 'nextstage' and 'shutdown' command, but you can return
                a custom command that will be handled ad end of the scheduler cycle.
                '''
                for job in cloned_jobs:
                    try:
                        job.execute(self.telemetry, self, scheduler_stage, cycle_commands)
                    except Exception as e:
                        logging.error("Job Execution Error: jobid %s error %s" % (job.jobid, e))

            '''
            Execute cycle commands added from the jobs. Nextstage and shutdown are handled by the scheduler and
            will not be propagated to jobs.
            '''
            for cmd in cycle_commands:
                logging.debug('Command %s triggered' % cmd)
                if cmd == 'nextstage':
                    if scheduler_stage == self.telemetry.stage():
                        self.vessel.control.activate_next_stage()
                elif cmd == 'shutdown':
                    self.shutdown = True
                else:
                    for job in cloned_jobs:
                        if not job.disabled and not job.expired:
                            try:
                                job.execute_custom_command(self.telemetry, self, scheduler_stage, cmd)
                            except Exception as e:
                                logging.error("Job Execution Error: jobid %s error %s" % (job.jobid, e))

            time.sleep(self.frequency)








