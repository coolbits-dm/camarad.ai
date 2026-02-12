"""
Phase 29 – AWS connector tests  (20 tests)
EC2, S3, Lambda, Overview, Cost Explorer, Reports, Test API, Status
"""
import unittest, requests

BASE = "http://127.0.0.1:5051"


class TestAWS(unittest.TestCase):

    # ── EC2 ────────────────────────────────────────────────────────────
    def test_ec2_all(self):
        r = requests.get(f"{BASE}/api/connectors/aws/ec2")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 12)
        self.assertTrue(all("instance_id" in i for i in data))

    def test_ec2_filter_running(self):
        r = requests.get(f"{BASE}/api/connectors/aws/ec2?status=running")
        data = r.json()
        self.assertTrue(len(data) >= 10)
        self.assertTrue(all(i["status"] == "running" for i in data))

    def test_ec2_filter_stopped(self):
        r = requests.get(f"{BASE}/api/connectors/aws/ec2?status=stopped")
        data = r.json()
        self.assertTrue(len(data) >= 2)
        self.assertTrue(all(i["status"] == "stopped" for i in data))

    def test_ec2_filter_az(self):
        r = requests.get(f"{BASE}/api/connectors/aws/ec2?az=us-east-1a")
        data = r.json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(all(i["az"] == "us-east-1a" for i in data))

    # ── S3 ─────────────────────────────────────────────────────────────
    def test_s3_all(self):
        r = requests.get(f"{BASE}/api/connectors/aws/s3")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 8)
        self.assertTrue(all("name" in b for b in data))

    def test_s3_filter_standard(self):
        r = requests.get(f"{BASE}/api/connectors/aws/s3?storage_class=STANDARD")
        data = r.json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(all(b["storage_class"] == "STANDARD" for b in data))

    def test_s3_filter_glacier(self):
        r = requests.get(f"{BASE}/api/connectors/aws/s3?storage_class=GLACIER")
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "camarad-archive")

    # ── Lambda ─────────────────────────────────────────────────────────
    def test_lambda_all(self):
        r = requests.get(f"{BASE}/api/connectors/aws/lambda")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 8)
        self.assertTrue(all("runtime" in f for f in data))

    def test_lambda_filter_python(self):
        r = requests.get(f"{BASE}/api/connectors/aws/lambda?runtime=python")
        data = r.json()
        self.assertTrue(len(data) >= 4)
        self.assertTrue(all("python" in f["runtime"].lower() for f in data))

    def test_lambda_filter_active(self):
        r = requests.get(f"{BASE}/api/connectors/aws/lambda?status=active")
        data = r.json()
        self.assertTrue(len(data) >= 7)
        self.assertTrue(all(f["status"] == "active" for f in data))

    def test_lambda_filter_inactive(self):
        r = requests.get(f"{BASE}/api/connectors/aws/lambda?status=inactive")
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "legacy-migrator")

    # ── Overview ───────────────────────────────────────────────────────
    def test_overview(self):
        r = requests.get(f"{BASE}/api/connectors/aws/overview")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["ec2_instances_total"], 12)
        self.assertEqual(d["s3_buckets"], 8)
        self.assertEqual(d["lambda_functions"], 8)
        self.assertIn("monthly_cost_trend", d)
        self.assertIn("service_breakdown", d)
        self.assertTrue(len(d["monthly_cost_trend"]) >= 6)
        self.assertTrue(len(d["service_breakdown"]) >= 5)

    # ── Cost Explorer ──────────────────────────────────────────────────
    def test_cost_explorer_all(self):
        r = requests.get(f"{BASE}/api/connectors/aws/cost-explorer")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(len(data) >= 6)
        self.assertIn("total", data[0])

    def test_cost_explorer_filter_service(self):
        r = requests.get(f"{BASE}/api/connectors/aws/cost-explorer?service=ec2")
        data = r.json()
        self.assertTrue(len(data) >= 6)
        self.assertTrue(all(d["service"] == "ec2" for d in data))

    # ── Reports ────────────────────────────────────────────────────────
    def test_reports_unified(self):
        r = requests.get(f"{BASE}/api/connectors/aws/reports")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        # 12 EC2 + 8 S3 + 8 Lambda + 6 Cost = 34
        self.assertTrue(len(data) >= 34)
        types = set(row["type"] for row in data)
        self.assertIn("EC2 Instance", types)
        self.assertIn("S3 Bucket", types)
        self.assertIn("Lambda Function", types)
        self.assertIn("Cost", types)

    # ── Test API ───────────────────────────────────────────────────────
    def test_api_call_ec2_describe(self):
        r = requests.post(f"{BASE}/api/connectors/aws/test-call",
                          json={"endpoint": "ec2-describe-instances"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("Reservations", d["response"]["body"])

    def test_api_call_s3_list(self):
        r = requests.post(f"{BASE}/api/connectors/aws/test-call",
                          json={"endpoint": "s3-list-buckets"})
        d = r.json()
        self.assertIn("Buckets", d["response"]["body"])

    def test_api_call_lambda_list(self):
        r = requests.post(f"{BASE}/api/connectors/aws/test-call",
                          json={"endpoint": "lambda-list-functions"})
        d = r.json()
        self.assertIn("Functions", d["response"]["body"])

    def test_api_call_cloudwatch(self):
        r = requests.post(f"{BASE}/api/connectors/aws/test-call",
                          json={"endpoint": "cloudwatch-get-alarms"})
        d = r.json()
        self.assertIn("MetricAlarms", d["response"]["body"])

    # ── Status ─────────────────────────────────────────────────────────
    def test_status_save_read(self):
        requests.post(f"{BASE}/api/connectors/aws",
                      json={"status": "Connected", "config": {"region": "us-east-1"}})
        r = requests.get(f"{BASE}/api/connectors")
        statuses = r.json()
        self.assertEqual(statuses.get("aws"), "Connected")


if __name__ == "__main__":
    unittest.main()
