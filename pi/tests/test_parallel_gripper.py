"""Parallel J6 calibration and motion on the Pi runtime's dry-run hardware."""
import json

import pytest
from fakes import Clock, FakeBus, FakePins

from thenar_pi import armcal, config
from thenar_pi.hw import PCA9685
from thenar_pi.robot import Robot


@pytest.fixture(autouse=True)
def parallel(monkeypatch):
    monkeypatch.setattr(config, "GRIPPER", "parallel")


def parallel_record(slope=36, open_gap=50):
    c = armcal.known()
    c.zero_us[5], c.us_per_deg[5], c.sign[5] = 600, slope, 1
    c.min_us[5], c.max_us[5] = 600, 600 + slope * open_gap
    c.crc = c.compute_crc()
    return c


def test_gripper_kind_env_default_and_override(monkeypatch):
    monkeypatch.delenv("THENAR_GRIPPER", raising=False)
    assert config._env_gripper() == "parallel"
    monkeypatch.setenv("THENAR_GRIPPER", "rotary")
    assert config._env_gripper() == "rotary"


def test_parallel_round_trip_and_servo_variants(tmp_path):
    for slope, gap in ((36, 50), (24, 75)):
        c = parallel_record(slope, gap)
        assert c.complete() and c.limits_deg(5) == pytest.approx((0, gap))
        assert armcal.save(tmp_path, c)
        back = armcal.load(tmp_path)
        assert back is not None and back.complete() and back.crc == c.crc
        assert back.pulse(5, 20) == pytest.approx(600 + 20 * slope)


def test_parallel_slope_and_gap_bounds():
    assert not armcal.known().valid()   # old rotary numbers cannot load as a parallel record
    for slope in (2, 90):
        assert not parallel_record(slope, 20).joint_ok(5)
    c = parallel_record(24, 75)
    c.min_us[5] = 576               # would describe a negative jaw gap
    assert not c.joint_ok(5)
    c = parallel_record(15, 50)
    c.max_us[5] = 2000              # 93.3 mm exceeds the specified stroke
    assert not c.joint_ok(5)


def test_config_and_slew_are_in_mm(tmp_path):
    armcal.save(tmp_path, parallel_record())
    clock = Clock()
    robot = Robot(PCA9685(FakeBus()), FakePins(), state_dir=str(tmp_path), clock=clock)
    robot.boot()
    cfg = json.loads(robot.config_msg()[1:])
    assert cfg["gripper"] == "parallel" and cfg["units"] == ["deg"] * 5 + ["mm"]
    assert cfg["velocity"][5] == 14 and cfg["hi"][5] == 50
    assert "gripper=parallel" in robot.calibrator("HELLO")[0]
    robot.handle("M 32")
    robot.handle("Q 5 40")
    for _ in range(10):
        clock.advance(0.01)
        robot.tick()
    assert robot.cur[5] == pytest.approx(1.4)
    robot.handle("V 5 50")
    assert robot.vel[5] == 14


def test_seed_known_refused_for_parallel(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "STATE_DIR", str(tmp_path))
    assert armcal.main(["armcal", "seed-known"]) == 1
    assert "rotary only" in capsys.readouterr().err
    assert not armcal.path(tmp_path).exists()
