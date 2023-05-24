import odrive
import time
import sys

start_time = time.time()
time_now = start_time
MAX_CONNECT_TIME = 10

while True:
    try:
        odrv0 = odrive.find_any()
        break
    except Exception:
        time_now = time.time()
    if time_now > start_time + MAX_CONNECT_TIME:
        raise IOError(f'could not connect to any ODrive within {MAX_CONNECT_TIME}s')

force_calibrate = '--calibrate' in sys.argv
calibrating = False
if force_calibrate or not odrv0.axis0.motor.is_calibrated:
    calibrating = True
    odrv0.axis0.requested_state = 3 #AXIS_STATE_FULL_CALIBRATION_SEQUENCE

if force_calibrate or not odrv0.axis1.motor.is_calibrated:
    calibrating = True
    odrv0.axis1.requested_state = 3 #AXIS_STATE_FULL_CALIBRATION_SEQUENCE

if calibrating:
    time.sleep(17)

if force_calibrate:
    exit() # exit after just calibrating if that's all we wanted to do

hard_spring = '--hard-spring' in sys.argv
spring_k = 100 if hard_spring else 2
overall_current_lim = 20 if hard_spring else 3
min_current = 5#TODO: REMOVE!!.5 if hard_spring else .15

limit = 1.0
if '--limit' in sys.argv:
    limit_str = sys.argv[sys.argv.index('--limit') + 1]
    limit = abs(float(limit_str))

ratio = 1.0
if '--ratio' in sys.argv:
    ratio_str = sys.argv[sys.argv.index('--ratio') + 1]
    try:
        if '/' in ratio_str:
            num, denom = ratio_str.split('/')
            ratio = float(num)/float(denom)
        else:
            ratio = float(ratio_str)
    except IndexError:
        raise ValueError('could not parse ratio.')
    if not hard_spring and (ratio == 0 or not .01 <= abs(ratio) <= 100):
        raise ValueError(f'turn factor {ratio} is out of bounds.')
    if hard_spring:
        ratio = 1 if ratio >= 0 else -1
        print(f'hard spring: ignoring ratio magnitude for safety. ratio is {ratio}')

sim_velocity = '--velocity' in sys.argv

bias = 0
if '--bias' in sys.argv:
    bias = float(sys.argv[sys.argv.index('--bias') + 1])

remote = '--remote' in sys.argv
if remote:
    from sync import AveragingServer

def config_axis(axis):
    axis.controller.config.vel_limit = 5 # turns per second
    axis.controller.config.vel_limit_tolerance = 5 # 500%
    axis.motor.config.current_lim = min_current # amp
    axis.motor.config.current_lim_margin = 30 # amp (allow fast input movement)
    axis.encoder.set_linear_count(0)

config_axis(odrv0.axis0)
config_axis(odrv0.axis1)

if remote:
    avg_server = AveragingServer(2)
try:
    odrv0.axis0.requested_state = 8 # AXIS_STATE_CLOSED_LOOP_CONTROL
    odrv0.axis1.requested_state = 8 # AXIS_STATE_CLOSED_LOOP_CONTROL

    dtime = 0
    pos0 = pos1 = None
    one_iter_done = False
    now_time = time.time()

    if remote:
        avg_server.start()
    while True:
        if sim_velocity and one_iter_done:
            old_pos0 = pos0
            old_pos1 = pos1
            old_time = now_time
            now_time = time.time()
            dtime = now_time - old_time
        pos0 = odrv0.axis0.encoder.pos_estimate
        pos1 = odrv0.axis1.encoder.pos_estimate
        if remote:
            avg_server.add_location(pos0)
            avg_server.add_location(pos1)
        if sim_velocity and one_iter_done:
            vel0 = (pos0 - old_pos0)/dtime
            vel1 = (pos1 - old_pos1)/dtime
            pos0 += dtime * vel0 * .8
            pos1 += dtime * vel1 * .8
        axis0_set = pos1*ratio
        axis1_set = pos0/ratio
        if -bias * axis0_set > 0: # don't allow bias to rotate past the start position
            axis0_set += bias
        if -bias * axis1_set > 0: # these account for positive or negative bias
            axis1_set += bias
        axis0_set = max(min(axis0_set, limit), -limit)
        axis1_set = max(min(axis1_set, limit), -limit)
        odrv0.axis0.controller.input_pos = axis0_set
        odrv0.axis1.controller.input_pos = axis1_set

        def current_func(err):
            i_out = min_current + spring_k*err
            #if err > .2:
            #    i += 1 * (err-.2)**2
            i_out = min(i_out, overall_current_lim)
            return i_out
        odrv0.axis0.motor.config.current_lim = current_func(abs(pos1 - axis1_set))
        odrv0.axis1.motor.config.current_lim = current_func(abs(pos0 - axis0_set))
        one_iter_done = True
finally:
    odrv0.axis0.requested_state = 1 # AXIS_STATE_IDLE
    odrv0.axis1.requested_state = 1 # AXIS_STATE_IDLE
    if remote:
        avg_server.cancel()

