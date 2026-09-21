import contextlib
import io
import unittest

from apiwells.models import ProbeResult, ResultStatus, SupportStatus
from apiwells.runner import DoctorRunner


class StaticProbe:
    def __init__(self, result):
        self.result = result

    def run(self):
        return self.result


class InvalidProbe:
    def run(self):
        return {"ok": True}


class DoctorRunnerTests(unittest.TestCase):
    def test_runner_preserves_probe_order(self):
        dns = ProbeResult(
            name="dns",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="DNS resolution succeeded.",
        )

        models = ProbeResult(
            name="models",
            status=ResultStatus.PASS,
            support=SupportStatus.SUPPORTED,
            summary="Models endpoint returned a valid model list.",
        )

        runner = DoctorRunner([
            StaticProbe(dns),
            StaticProbe(models),
        ])

        results = runner.run()

        self.assertEqual(
            [result.name for result in results],
            ["dns", "models"],
        )

    def test_runner_does_not_print(self):
        result = ProbeResult(
            name="dns",
            status=ResultStatus.PASS,
            support=SupportStatus.NOT_APPLICABLE,
            summary="DNS resolution succeeded.",
        )

        runner = DoctorRunner([StaticProbe(result)])

        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            runner.run()

        self.assertEqual(output.getvalue(), "")

    def test_runner_rejects_invalid_probe_result(self):
        runner = DoctorRunner([InvalidProbe()])

        with self.assertRaises(TypeError):
            runner.run()


if __name__ == "__main__":
    unittest.main()