import unittest
from src.metrics.throughput import calculate_throughput
from src.metrics.active_users import calculate_active_users
from src.metrics.events_by_type import calculate_events_by_type
from src.metrics.top_products import calculate_top_viewed_products, calculate_top_purchased_products
from src.metrics.purchases_by_region import calculate_purchases_by_region
from src.metrics.conversion import calculate_conversion
from src.metrics.trends import calculate_trends

class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.sample_events = [
            {
                "event_type": "VIEW_PRODUCT",
                "user_id": "USR1",
                "region": "LIMA",
                "payload": {"product_id": "P1", "product_name": "Prod 1", "category": "TEC"}
            },
            {
                "event_type": "VIEW_PRODUCT",
                "user_id": "USR1",
                "region": "LIMA",
                "payload": {"product_id": "P2", "product_name": "Prod 2", "category": "TEC"}
            },
            {
                "event_type": "ADD_TO_CART",
                "user_id": "USR1",
                "region": "LIMA",
                "payload": {"product_id": "P1"}
            },
            {
                "event_type": "PURCHASE",
                "user_id": "USR1",
                "region": "LIMA",
                "payload": {
                    "total_amount": 1500.0,
                    "items": [
                        {"product_id": "P1", "product_name": "Prod 1", "category": "TEC", "quantity": 1, "subtotal": 1500.0}
                    ]
                }
            },
            {
                "event_type": "VIEW_PRODUCT",
                "user_id": "USR2",
                "region": "AREQUIPA",
                "payload": {"product_id": "P1", "product_name": "Prod 1", "category": "TEC"}
            }
        ]

    def test_throughput(self):
        res = calculate_throughput(self.sample_events, window_duration_sec=10)
        self.assertEqual(res["total_events"], 5)
        self.assertEqual(res["events_per_second"], 0.5)

    def test_active_users(self):
        res = calculate_active_users(self.sample_events)
        self.assertEqual(res["active_users_count"], 2)

    def test_events_by_type(self):
        res = calculate_events_by_type(self.sample_events)
        self.assertEqual(res["counts"]["VIEW_PRODUCT"], 3)
        self.assertEqual(res["counts"]["ADD_TO_CART"], 1)
        self.assertEqual(res["counts"]["PURCHASE"], 1)

    def test_top_products(self):
        viewed = calculate_top_viewed_products(self.sample_events)
        self.assertEqual(viewed["top_products"][0]["product_id"], "P1")
        self.assertEqual(viewed["top_products"][0]["count"], 2)

        purchased = calculate_top_purchased_products(self.sample_events)
        self.assertEqual(len(purchased["top_products"]), 1)
        self.assertEqual(purchased["top_products"][0]["product_id"], "P1")

    def test_purchases_by_region(self):
        res = calculate_purchases_by_region(self.sample_events)
        self.assertEqual(len(res["regions"]), 1)
        self.assertEqual(res["regions"][0]["region"], "LIMA")
        self.assertEqual(res["regions"][0]["total_amount"], 1500.0)

    def test_conversion(self):
        res = calculate_conversion(self.sample_events)
        self.assertEqual(res["views_count"], 3)
        self.assertEqual(res["cart_additions_count"], 1)
        self.assertEqual(res["purchases_count"], 1)
        self.assertAlmostEqual(res["overall_conversion_rate"], 33.33, places=1)

    def test_trends(self):
        res = calculate_trends(self.sample_events)
        self.assertEqual(res["events_count"], 5)
        self.assertEqual(res["active_users"], 2)
        self.assertEqual(res["purchases_count"], 1)
        self.assertEqual(res["total_revenue"], 1500.0)

if __name__ == "__main__":
    unittest.main()
