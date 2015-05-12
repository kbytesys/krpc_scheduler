__author__ = 'Andrea'

import krpc.client
import krpc.service
from threading import Thread, RLock
import time


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

    def execute_exit_stage(self, telemetry, scheduler, stage):
        pass

    def execute_enter_stage(self, telemetry, scheduler, stage):
        pass

    def execute_custom_command(self, telemetry, scheduler, stage, command):
        pass


# noinspection PyUnresolvedReferences
class KRPCVesselScheduler(Thread):
    def __init__(self, conn: krpc.client.Client, telemetry: KRPCVesselTelemetry=None, frequency=0.5):
        Thread.__init__(self)
        self.conn = conn
        self.telemetry = telemetry
        self.space_center = conn.space_center
        self.vessel = conn.space_center.active_vessel
        self.frequency = frequency
        self.jobqueue = []
        self.queuelock = RLock()
        self.shutdown = True

        if telemetry is None:
            self.telemetry = KRPCVesselTelemetry(self.conn, self.vessel)

    def register_job(self, job: KRPCJob):
        self.queuelock.acquire()
        self.jobqueue.append(job)
        self.jobqueue.sort(key=lambda x: x.priority, reverse=True)
        self.queuelock.release()

    def unregister_job(self, jobid):
        self.queuelock.acquire()
        for job in self.jobqueue:
            if job.jobid == jobid:
                self.jobqueue.remove(job)
                break
        self.queuelock.release()

    def run(self):
        self.shutdown = False
        scheduler_stage = self.telemetry.stage()
        while not self.shutdown:
            self.queuelock.acquire()
            try:
                if scheduler_stage < self.telemetry.stage():
                    print("Scheduler stage not coerent!!! Vechile switch???")
                    self.shutdown = True
                    self.queuelock.release()
                    break

                if scheduler_stage != self.telemetry.stage():
                    while scheduler_stage != self.telemetry.stage():
                        print("Change stage from %d to %d" % (scheduler_stage, self.telemetry.stage()))
                        for job in self.jobqueue:
                            job.execute_exit_stage(self.telemetry, self, scheduler_stage)
                        scheduler_stage -= 1
                        for job in self.jobqueue:
                            job.execute_enter_stage(self.telemetry, self, scheduler_stage)

                toremove = []
                cycle_commands = set()
                for job in self.jobqueue:
                    if not job.disabled and (job.stage is None or job.stage == scheduler_stage):
                        job.execute(self.telemetry, self, scheduler_stage, cycle_commands)
                    if job.expired:
                        toremove.append(job)

                # remove expired elements
                for job in toremove:
                    self.jobqueue.remove(job)

                # Execute scheduler cycle command
                for cmd in cycle_commands:
                    if cmd == 'nextstage':
                        if scheduler_stage == self.telemetry.stage():
                            self.vessel.control.activate_next_stage()
                    elif cmd == 'shutdown':
                        self.shutdown = True
                    else:
                        # custom command!
                        for job in self.jobqueue:
                            if not job.disabled and (job.stage is None or job.stage == scheduler_stage):
                                job.execute_custom_command(self.telemetry, self, scheduler_stage, cmd)

                time.sleep(self.frequency)
                self.queuelock.release()
            except Exception as e:
                self.queuelock.release()
                print(e)
                time.sleep(1)








