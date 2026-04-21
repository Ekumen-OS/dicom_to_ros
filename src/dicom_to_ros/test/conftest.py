import pytest
import rclpy


@pytest.fixture(scope="session", autouse=True)
def rclpy_init():
    rclpy.init()
    yield
    rclpy.shutdown()
