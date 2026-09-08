# bci_core

Signal processing, and nothing else. No Qt, no Cortex, no drone — these classes
take numbers in and give numbers out, which is what makes them testable without
hardware. Every measurement quoted in
[HOW_IT_WORKS.md](../HOW_IT_WORKS.md) came from driving them directly or
replaying a recorded session through them.

`drone_controller.TelloDroneClient` owns one `ProgramSimulator` and reaches
through it for both processors.

---

## `processor.py` — `QuaternionProcessor`

Turns the headset's orientation into the drone's heading.

The name is a leftover: `calculate_cursor_movement()` dates from a cursor-control
ancestor and still returns the `(dx, dy)` pair that steering used to be built
on. **Nothing steers with that return value any more.** The output that matters
is the attribute it sets on the way through:

```python
qp.head_heading_deg   # where the drone should point, degrees off centre
qp.head_yaw_deg       # the head's own angle, smoothed and drift-corrected
qp.head_yaw_raw_deg   # the same before smoothing
```

`_update_heading()` is the real entry point. It is position control, not rate
control — the head's angle *is* the heading, so nothing accumulates and letting
your head return to centre returns the drone to centre. The full derivation,
and why the rate model was removed, is in
[HOW_IT_WORKS.md section 3](../HOW_IT_WORKS.md#3-steering-the-heads-angle-is-the-heading).

Shape of it: relative quaternion, `asin` for the yaw angle, moving average,
subtractive deadzone, cubic expo in normalised units, clamp.

### Calibration

`accumulate_calibration_sample()` collects 60 frames, then averages and
normalises them into the reference. A single frame is not enough — that frame
arrives while the wearer is still settling the headset, and any error in it
becomes a permanent offset. `calibrate()` sets a reference directly, and
`reset()` clears everything so the next 60 frames rebuild it.

Both clear the smoothing buffers and zero the drift state. Recenter and
run-start both come through here.

### Drift correction

`drift_correction` defaults to `False`. Leave it that way. It is an alpha-beta
tracker that cannot distinguish a slowly drifting gyro from a small turn
somebody is holding on purpose, and in a real session it learned the steering:
+40°/min against a true 1.81. The reasoning and the numbers are in
HOW_IT_WORKS.md.

### Testing it

`time_source` is injectable, which is the whole reason drift behaviour is
measurable rather than guessed at:

```python
clock = {"t": 0.0}
qp = QuaternionProcessor()
qp.time_source = lambda: clock["t"]
qp.calibrate(1.0, 0.0, 0.0, 0.0)

for i in range(60 * 32):
    clock["t"] = i / 32.0
    half = math.radians(head_angle_at(clock["t"])) / 2
    qp.calculate_cursor_movement(math.cos(half), 0.0, 0.0, math.sin(half))
    print(qp.head_heading_deg)
```

A pure yaw rotation of `d` degrees is `(cos(d/2), 0, 0, sin(d/2))`, which is
enough to exercise every steering path. Feed a `motion-capture.csv` through the
same loop to replay a real session.

---

## `mental.py` — `MentalCommandProcessor`

A threshold lookup, and deliberately no more than that. Cortex has already done
the classification; this decides whether to act on it.

```python
action, auto_release, should_execute = mp.process_command("push", 0.72)
```

It walks `mappings` — the `mental_mappings` list from `config.json` — for one
whose `command` matches, then compares `power` against that entry's `threshold`.
No state, no history, no hysteresis. Ramping and expiry live in
`DroneAdapter`, not here.

The default mapping is `push` to `MoveForward`, with `pull`, `lift` and `drop`
mapped to `None`. Take-off and landing are unused — there is no real drone.

---

## `program.py` — `ProgramSimulator`

A thin adapter between the controller's stream callbacks and the two processors.
Despite the name it simulates nothing and holds no flight state.

```python
dx, dy = program.receive_motion([ts, _, _, w, x, y, z])   # indices 3..6
action, auto_release, fire = program.receive_mental([ts, command, power])
```

`receive_motion` unpacks `w, x, y, z` from positions 3 to 6, feeds them to the
quaternion processor, and returns its `(dx, dy)`. Callers use that return only
for logging now; the steering value is read off
`program.quaternion_processor.head_heading_deg`.

Until the processor reports `is_calibrated`, every frame is fed to
`accumulate_calibration_sample()` and `(0, 0)` is returned. That branch was
dead for a while and calibration ran off a single frame — worth knowing, because
the symptom was a permanent steering offset with no obvious cause.

---

## `ai_helpers.py`

Quaternion constants and test vectors carried over from the original C#
blueprint. Nothing imports it. Useful as hand-checkable inputs when poking at
the processor, and harmless to delete otherwise.
