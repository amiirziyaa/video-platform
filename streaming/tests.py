from django.test import TestCase, RequestFactory
from django.urls import reverse

from .models import User, SubscriptionPlan, Payment
from .services import SubscriptionService, MockBankGateway


class SubscriptionServiceTests(TestCase):
    """Tests for the SubscriptionService."""

    def setUp(self):
        """Set up common test data."""
        # Arrange: Create necessary objects for the test
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            phone_number="09123456789"  # Add this line
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Premium", price=10000, duration_days=30, level=2
        )
        # We use a RequestFactory to create a mock request object
        self.factory = RequestFactory()

    def test_start_payment_process_success(self):
        """
        Test that start_payment_process successfully initiates a payment
        with a mock gateway.
        """
        # Arrange:
        # 1. Create a mock gateway that will always succeed
        mock_gateway = MockBankGateway(success_rate=1.0)
        # 2. Instantiate our service and INJECT the mock gateway
        # This is the key to unit testing: we control the dependency.
        service = SubscriptionService(gateway=mock_gateway)
        # 3. Create a fake request object
        request = self.factory.get(reverse("dashboard")) # The URL doesn't matter much here
        request.user = self.user

        # Act:
        # Run the method we want to test
        payment_obj, payment_url = service.start_payment_process(
            self.user, self.plan, request
        )

        # Assert:
        # Check that the results are correct
        self.assertIsNotNone(payment_obj)
        self.assertIsNotNone(payment_url)
        
        # Check that a Payment object was created in the database
        self.assertEqual(Payment.objects.count(), 1)
        created_payment = Payment.objects.first()
        
        self.assertEqual(created_payment.user, self.user)
        self.assertEqual(created_payment.plan, self.plan)
        self.assertEqual(created_payment.amount, self.plan.price)
        self.assertNotEqual(created_payment.authority_code, "") # Should have an authority code
        self.assertEqual(created_payment.status, Payment.Status.PENDING)

    def test_start_payment_process_failure(self):
        """
        Test that start_payment_process handles a failure from the gateway.
        """
        # Arrange:
        # 1. Create a mock gateway that is configured to always fail.
        mock_gateway = MockBankGateway(success_rate=0.0)
        # 2. Instantiate our service with the failing mock gateway.
        service = SubscriptionService(gateway=mock_gateway)
        # 3. Create a fake request.
        request = self.factory.get(reverse("dashboard"))
        request.user = self.user

        # Act & Assert:
        # We test that a ValueError is raised using this special context manager.
        # The test will only pass if the code inside this 'with' block
        # raises a ValueError.
        with self.assertRaises(ValueError):
            service.start_payment_process(self.user, self.plan, request)

        # Assert (Post-Exception):
        # We also check the database to make sure the payment object was
        # created but correctly marked as 'failed'.
        self.assertEqual(Payment.objects.count(), 1)
        failed_payment = Payment.objects.first()
        self.assertEqual(failed_payment.status, Payment.Status.FAILED)
        self.assertEqual(failed_payment.user, self.user)