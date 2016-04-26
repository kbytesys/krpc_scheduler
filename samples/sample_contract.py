"""
Sample contract jobs. We need to test the decoupler at 13000 <= altitude <= 14000 with 300 <= speed <= 1200.
We want to handle prelaunch, solid booster and reenter too.
"""
import sys
from kbyte.krpc import *
import krpc
conn = krpc.connect(name='Contract Experiment')


# use console for log
root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

kslog = logging.getLogger("krpc_scheduler")
kslog.setLevel(logging.DEBUG)
log = logging.getLogger("main")


class SolidDetach(KRPCJob):
    def __init__(self):
        KRPCJob.__init__(self, 'detach_booster')

    def execute(self, telemetry, scheduler, stage, cycle_commands: set, is_active: bool):
        if not is_active:
            return

        if telemetry.vessel.resources.amount('SolidFuel') == 0:
            kslog.info('Booster separation')
            self.disabled = True
            self.expired = True
            cycle_commands.add('nextstage')


class PreLaunch(KRPCJob):
    def __init__(self):
        KRPCJob.__init__(self, 'prelaunch_settings')

    def execute(self, telemetry, scheduler, stage, cycle_commands, is_active: bool):
        if not is_active:
            return

        telemetry.vessel.control.sas = True
        telemetry.vessel.control.throttle = 1
        self.expired = True


class ExperimentJob(KRPCJob):
    def __init__(self):
        KRPCJob.__init__(self, 'test_part', stage=2)

    def execute(self, telemetry, scheduler, stage, cycle_commands: set, is_active: bool):
        if not is_active:
            return

        kslog.debug("speed: %s\nalt: %s" % (telemetry.vessel_orbit_speed(), telemetry.altitude()))
        if telemetry.altitude() > 14000:
            kslog.warning("Experiment failed!!! ABORT ABORT")
            telemetry.vessel.control.throttle = 0
            telemetry.vessel.control.sas = False
            cycle_commands.add('shutdown')
            return

        if telemetry.altitude() >= 13000:
            if 300 <= telemetry.vessel_orbit_speed() <= 1200:
                kslog.info("Engage decoupler.")
                telemetry.vessel.control.sas = False
                telemetry.vessel.control.throttle = 0
                time.sleep(0.1)
                cycle_commands.add('nextstage')
                self.disabled = True


class DeployPara(KRPCJob):
    def __init__(self):
        KRPCJob.__init__(self, 'mk16deploy', stage=1)

    def execute(self, telemetry, scheduler, stage, cycle_commands: set, is_active: bool):
        if not is_active:
            return

        if telemetry.altitude() <= 5000:
            kslog.info("Deploy chutes")
            cycle_commands.add('nextstage')
            cycle_commands.add('shutdown')

scheduler = KRPCVesselScheduler(conn)
scheduler.register_job(SolidDetach())
scheduler.register_job(PreLaunch())
scheduler.register_job(ExperimentJob())
scheduler.register_job(DeployPara())
scheduler.start()
scheduler.join()


