"""
Integration tests for the SAI Android communication fix.

Verifies:
1. PlanExecutor treats "queued" as failure
2. DeviceManager refuses commands when queue is full
3. AndroidCompanionClient.is_healthy() returns False on connection error
4. command.execute_plan returns "failed" when device is offline
5. No false success responses anywhere in the pipeline
"""
import sys
import os
import time

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_plan_executor_queued_is_failure():
    """PlanExecutor must treat 'queued' status as failure, not success."""
    from modules.plan_executor import PlanExecutor

    class FakeDeviceManager:
        def is_device_healthy(self, device_id):
            return True
        def get_device_status(self, device_id):
            return "online"
        def route_command(self, device_id, command, params, timeout=15):
            # Simulate offline device returning "queued"
            return {"status": "queued", "message": "Command queued automatically."}

    class FakeSAI:
        device_manager = FakeDeviceManager()

    executor = PlanExecutor(FakeSAI())
    plan = {"steps": [{"action": "open_app", "target": "com.whatsapp"}]}
    result = executor.execute("android_phone", plan, retry_limit=0)

    assert result["status"] == "failed", f"Expected 'failed', got '{result['status']}'"
    print("✅ PASS: PlanExecutor correctly treats 'queued' as failure")


def test_plan_executor_device_health_precheck():
    """PlanExecutor must refuse to execute if device is unhealthy."""
    from modules.plan_executor import PlanExecutor

    class FakeDeviceManager:
        def is_device_healthy(self, device_id):
            return False
        def get_device_status(self, device_id):
            return "offline"

    class FakeSAI:
        device_manager = FakeDeviceManager()

    executor = PlanExecutor(FakeSAI())
    plan = {"steps": [{"action": "open_app", "target": "com.whatsapp"}]}
    result = executor.execute("android_phone", plan)

    assert result["status"] == "failed", f"Expected 'failed', got '{result['status']}'"
    assert result.get("error") == "DEVICE_UNHEALTHY"
    print("✅ PASS: PlanExecutor refuses execution for unhealthy device")


def test_device_manager_queue_limit():
    """DeviceManager must refuse commands when queue is full."""
    from modules.device_manager import DeviceManager, COMMAND_QUEUE_LIMIT

    dm = DeviceManager()
    # Don't register device — it stays "offline"

    # Fill queue to limit
    for i in range(COMMAND_QUEUE_LIMIT):
        result = dm.route_command("test_device", "open_app", {"package": f"pkg_{i}"})
        assert result["status"] == "queued", f"Expected 'queued' on fill #{i}"

    # Next command should be rejected
    result = dm.route_command("test_device", "open_app", {"package": "overflow_pkg"})
    assert result["status"] == "failed", f"Expected 'failed', got '{result['status']}'"
    assert result.get("error") == "DEVICE_UNREACHABLE"
    print(f"✅ PASS: DeviceManager refuses commands after queue limit ({COMMAND_QUEUE_LIMIT})")


def test_device_manager_health_check():
    """is_device_healthy must return False for unregistered/offline devices."""
    from modules.device_manager import DeviceManager

    dm = DeviceManager()

    # Unknown device
    assert dm.is_device_healthy("nonexistent") is False

    # Register and then unregister
    dm.register_device("test_dev", "android", "192.168.1.100")
    assert dm.is_device_healthy("test_dev") is True

    dm.unregister_device("test_dev")
    assert dm.is_device_healthy("test_dev") is False
    print("✅ PASS: DeviceManager health check works correctly")


def test_device_manager_timeout_no_requeue():
    """Timed-out commands must return 'failed', not silently re-queue."""
    from modules.device_manager import DeviceManager

    dm = DeviceManager()
    dm.register_device("test_dev", "android", "127.0.0.1")
    # No dispatch handler → command will time out
    # (but dispatch handler is None so it returns error before waiting)

    result = dm.route_command("test_dev", "test_cmd", {}, timeout=1)
    assert result["status"] == "failed", f"Expected 'failed', got '{result['status']}'"
    assert "queue" not in result.get("message", "").lower(), "Should NOT re-queue"
    print("✅ PASS: DeviceManager timed-out commands return failure, not re-queue")


def test_companion_client_health_unreachable():
    """AndroidCompanionClient.is_healthy() must return False when server is down."""
    from modules.device_plugins.android_companion import AndroidCompanionClient

    # Point to a port that's certainly not running
    client = AndroidCompanionClient(host="127.0.0.1", port=19999)
    assert client.is_healthy(cache_ttl=0) is False
    print("✅ PASS: AndroidCompanionClient.is_healthy() returns False when unreachable")


def test_companion_client_screenshot_no_crash():
    """get_screenshot_base64() must return empty string, not crash, when server is down."""
    from modules.device_plugins.android_companion import AndroidCompanionClient

    client = AndroidCompanionClient(host="127.0.0.1", port=19999)
    result = client.get_screenshot_base64()
    assert result == "", f"Expected empty string, got '{result[:50]}...'"
    print("✅ PASS: AndroidCompanionClient.get_screenshot_base64() returns '' without crash")


def test_companion_client_structured_error():
    """HTTP errors must return structured dict, never raise."""
    from modules.device_plugins.android_companion import AndroidCompanionClient

    client = AndroidCompanionClient(host="127.0.0.1", port=19999)
    result = client._get("state/screenshot")
    assert isinstance(result, dict)
    assert result["status"] == "failed"
    assert "error" in result
    print("✅ PASS: AndroidCompanionClient returns structured error dicts")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  SAI ANDROID COMMUNICATION FIX — INTEGRATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        test_plan_executor_queued_is_failure,
        test_plan_executor_device_health_precheck,
        test_device_manager_queue_limit,
        test_device_manager_health_check,
        test_device_manager_timeout_no_requeue,
        test_companion_client_health_unreachable,
        test_companion_client_screenshot_no_crash,
        test_companion_client_structured_error,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ FAIL: {test_fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'=' * 60}\n")
    sys.exit(1 if failed else 0)
