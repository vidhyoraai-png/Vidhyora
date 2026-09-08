from django.test import TestCase
from django.urls import resolve
from django.apps import apps


class AIOnlyTests(TestCase):
    def test_ai_home_and_endpoints_are_preserved(self):
        self.assertEqual(resolve('/').url_name, 'home')
        self.assertEqual(resolve('/AI/api/send/').url_name, 'ai_chat_send')
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_store_endpoints_are_gone(self):
        for path in ('/store/', '/store/dashboard/products/', '/store/dashboard/categories/', '/store/dashboard/orders/'):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_store_models_are_gone_and_ai_models_remain(self):
        names = {model.__name__ for model in apps.get_app_config('myapp').get_models()}
        self.assertFalse(names & {'Product', 'Category', 'Cart', 'CartItem', 'Review', 'ContactLead'})
        self.assertTrue({'AIConversation', 'AIMessage', 'StoreProfile', 'Payment', 'Order', 'PWASettings', 'SiteCustomization'} <= names)
