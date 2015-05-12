import krpc.client
import krpc.service
from threading import Thread, RLock
import time
import logging

log = logging.getLogger('krpc_scheduler')


class KRPCVesselTelemetry():
    """
    Base vessel telemetry class with some common streamed data. You can still subclass or add attributes if you need more
    telemetry data
    """
    def __init__(self, conn, vessel):
        # Base telemetry
        self.conn = conn
        self.space_center = conn.space_center
        self.vessel = vessel
        self.ut = conn.add_stream(getattr, conn.space_center, 'ut')
        self.altitude = conn.add_stream(getattr, vessel.flight(), 'mean_altitude')
        self.stage = conn.add_stream(getattr, vessel.control, 'current_stage')
        self.apoapsis = conn.add_stream(getattr, vessel.orbit, 'apoapsis_altitude')
        self.periapsis = conn.add_stream(getattr, vessel.orbit, 'periapsis_altitude')
        self.eccentricity = conn.add_stream(getattr, vessel.orbit, 'eccentricity')
        self.vessel_orbit_speed = conn.add_stream(getattr, vessel.flight(vessel.orbit.body.reference_frame), 'speed')


    def add_vessel_flight_telemetry(self, attrib_name, proto_name):
        """
        Add a new attribute from vessel.flight() generic data
        """
        setattr(self, attrib_name, self.conn.add_stream(getattr, self.vessel.flight(), proto_name))

class KRPCVesselScheduler(Thread):
    pass


class KRPCJob():
    """
    Abstract class for scheduler jobs. You can create stage related jobs or always active jobs. Every job have got also an
    id (you have to assure that it is unique, if you want to remove them by id) and a priority value. Greater priority value
    means higher priority. You can disable/enable the job at your choice. When you set the expired field to true, the
    scheduler will remove the job.
    """
    def __init__(self, jobid, priority=10, stage=None):
        self.priority = priority
        self.stage = stage
        self.jobid = jobid
        self.disabled = False
        self.expired = False

    def execute(self, telemetry: KRPCVesselTelemetry, scheduler: KRPCVesselScheduler, stage, cycle_commands: set):
        """
        Execute the job. You can perform every action to vessel through the krpc api, but don't change the stage here. Use
        the cycle_commands set instead. If you add "nextstage" to the set, the scheduler will perform a stage change at
        end of its cycle. You can also add "shutdown" to abort the whole scheduler or you can add custom string command
        that will be managed by jobs at the end of scheduler cycle.
        """
        pass

    def execute_exit_stage(self, telemetry: KRPCVesselTelemetry, scheduler: KRPCVesselScheduler, stage, cycle_commands: set):
        """
        Perform commands at stage change. Look execute method doc for more info.
        """
        pass

    def execute_enter_stage(self, telemetry: KRPCVesselTelemetry, scheduler: KRPCVesselScheduler, stage, cycle_commands: set):
        """
        Perform commands at stage change. Look execute method doc for more info.
        """
        pass

    def execute_custom_command(self, telemetry: KRPCVesselTelemetry, scheduler: KRPCVesselScheduler, stage, command):
        """
        Execute a custom command at end of scheduler cycle. Look execute method doc for more info.
        """
        pass

    def remove_from_scheduler(self, scheduler: KRPCVesselScheduler):
        """
        Method called when the scheduler remove this job. You can use it when you need to perform some cleanups.
        """
        pass


# noinspection PyUnresolvedReferences
class KRPCVesselScheduler(Thread):
    """
    Scheduler class, you can perform scheduler jobs with a configurable frequency
    """
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

    def register_job(self, job: KRPCJob):
        """
        Register a job in the scheduler
        """
        self.queuelock.acquire()
        self.joblist.append(job)
        self.joblist.sort(key=lambda x: x.priority, reverse=True)
        self.queuelock.release()

    def unregister_job(self, jobid):
        """
        Remove a job from the scheduler by jobid
        """
        self.queuelock.acquire()
        for job in self.joblist:
            if job.jobid == jobid:
                self.joblist.remove(job)
                job.remove_from_scheduler(self)
                break
        self.queuelock.release()

    def unregister_job_object(self, job: KRPCJob):
        """
        Remove a job from the scheduler by job object
        """
        self.queuelock.acquire()
        try:
            self.joblist.remove(job)
            job.remove_from_scheduler(self)
        except ValueError:
            pass
        self.queuelock.release()

    def run(self):
        """
        Run the scheduler. In every cycle the scheduler manege the job list cleanup from expired items, manage stage changes,
        execute allowed jobs by status and current stage and perform end cycle commands requested by jobs. Please check the
        KRPCJob doc for better infos.
        """
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
                    log.debug("Job %s allowed in this scheduler cycle" % job.jobid)

            for job in toremove:
                self.unregister_job_object(job)
                log.debug("Job %s removed from scheduler." % job.jobid)

            self.queuelock.release()

            '''
            Check the current stage, if the scheduler stage is minor of telemetry stage, we have switched vessel or
            reverted the flight. Abort the scheduler to avoid an atomic fallout.
            '''
            if scheduler_stage < self.telemetry.stage():
                log.error("Scheduler stage not coerent!!! Vechile switch???")
                cycle_commands = ('shutdown',)

            else:

                cycle_commands = set()

                '''
                React to stage changes, execute job's exit and enter events until the right stage is reached.
                '''
                if scheduler_stage != self.telemetry.stage():
                    while scheduler_stage != self.telemetry.stage():
                        log.info("Change stage from %d to %d" % (scheduler_stage, self.telemetry.stage()))
                        for job in cloned_jobs:
                            try:
                                job.execute_exit_stage(self.telemetry, self, scheduler_stage, cycle_commands)
                            except Exception as e:
                                log.error("Job Exit Stage error: jobid %s stage %s error %s" %
                                              (job.jobid, scheduler_stage, e))
                        scheduler_stage -= 1
                        for job in cloned_jobs:
                            try:
                                job.execute_enter_stage(self.telemetry, self, scheduler_stage, cycle_commands)
                            except Exception as e:
                                log.error("Job Enter Stage error: jobid %s stage %s error %s" %
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
                        log.error("Job Execution Error: jobid %s error %s" % (job.jobid, e))

            '''
            Execute cycle commands added from the jobs. Nextstage and shutdown are handled by the scheduler and
            will not be propagated to jobs.
            '''
            for cmd in cycle_commands:
                log.debug('Command %s triggered' % cmd)
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
                                log.error("Job Execution Error: jobid %s error %s" % (job.jobid, e))

            time.sleep(self.frequency)








