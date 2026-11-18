import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import User
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.ai_usage_alerts import AIUsageLimitAlert, qualifies, identity, send_limit_alert, alert_view


class UsageAlertsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.shop = SimpleNamespace(id='shop-one', name='Test Shop', slug='shop-one',
            stripe_subscription_id='sub-one', highlevel_location_id='loc-one')
        self.db.add(User(id='owner-one', shop_id='shop-one', name='Owner', email='owner@example.com',
            password_hash='unused', role='owner', is_active=True))
        self.db.add(DayTelloVoicemailShopSettings(shop_id='shop-one', location_id='loc-one',
            receiving_number='+12405550100', owner_phone='+12405550101', notifications_enabled=True))
        self.db.commit()
        self.billing = {'metered': True, 'usage_available': True, 'status': 'active',
            'included_minutes': 250, 'overage_rate_cents': 29, 'minutes_used': 250,
            'period_start': '2026-11-18T15:00:13+00:00', 'period_end': '2026-12-18T15:00:13+00:00'}
        self.env = patch.dict(os.environ, {'RESEND_API_KEY':'test-not-real', 'HIGHLEVEL_LOCATION_ID':'loc-one',
            'HIGHLEVEL_SMS_FROM_NUMBER':'+12405550102', 'CHAIRTIME_FRONTEND_URL':'https://www.daytello.com'})
        self.env.start()
        self.email = patch('app.ai_usage_alerts.httpx.post', return_value=SimpleNamespace(is_success=True, status_code=200)).start()
        self.sms = patch('app.routes.reminders.send_highlevel_sms', return_value={'success':True}).start()
        self.recipient = patch('app.voicemail_owner_verification.verified_owner_recipient', return_value='+12405550101').start()

    def tearDown(self):
        patch.stopall()
        self.db.close()
        self.engine.dispose()

    def test_once_per_channel_per_cycle(self):
        send_limit_alert(self.db, self.shop, self.billing)
        send_limit_alert(self.db, self.shop, self.billing)
        self.assertEqual(self.email.call_count, 1)
        self.assertEqual(self.sms.call_count, 1)
        self.assertEqual(alert_view(self.db, self.shop, self.billing)['sms_state'], 'accepted')

    def test_new_cycle_gets_one_new_alert(self):
        send_limit_alert(self.db, self.shop, self.billing)
        self.billing.update(period_start='2026-12-18T15:00:13+00:00', period_end='2027-01-18T15:00:13+00:00')
        send_limit_alert(self.db, self.shop, self.billing)
        self.assertEqual(self.email.call_count, 2)
        self.assertEqual(self.sms.call_count, 2)

    def test_below_threshold_trial_and_legacy_do_not_send(self):
        for overrides in ({'minutes_used':249.999}, {'status':'trialing'}, {'metered':False},
                          {'usage_available':False}, {'included_minutes':1000}, {'status':'canceled'}):
            self.assertFalse(send_limit_alert(self.db, self.shop, {**self.billing, **overrides}))
        self.email.assert_not_called()
        self.sms.assert_not_called()

    def test_unknown_email_does_not_resend_or_block_text(self):
        self.email.side_effect = TimeoutError()
        send_limit_alert(self.db, self.shop, self.billing)
        send_limit_alert(self.db, self.shop, self.billing)
        self.assertEqual(self.email.call_count, 1)
        self.assertEqual(self.sms.call_count, 1)
        self.assertEqual(alert_view(self.db, self.shop, self.billing)['email_state'], 'unknown')

    def test_unverified_phone_is_not_texted(self):
        self.recipient.side_effect = ValueError('not verified')
        send_limit_alert(self.db, self.shop, self.billing)
        self.sms.assert_not_called()
        self.email.assert_called_once()
        self.assertEqual(alert_view(self.db, self.shop, self.billing)['sms_state'], 'unavailable')

    def test_ambiguous_sms_not_retried(self):
        self.sms.return_value = {'success':False, 'step':'message'}
        send_limit_alert(self.db, self.shop, self.billing)
        send_limit_alert(self.db, self.shop, self.billing)
        self.assertEqual(self.sms.call_count, 1)
        self.assertEqual(alert_view(self.db, self.shop, self.billing)['sms_state'], 'unknown')

    def test_tenant_and_subscription_scoped_identity(self):
        self.assertNotEqual(identity('shop1','sub1','date'), identity('shop2','sub1','date'))
        self.assertNotEqual(identity('shop1','sub1','date'), identity('shop1','sub2','date'))
        self.assertIsNone(alert_view(self.db, self.shop, {**self.billing, 'metered':False}))

    def test_sms_body_and_recipient_are_explicit(self):
        send_limit_alert(self.db, self.shop, self.billing)
        args, kwargs = self.sms.call_args
        self.assertEqual(args[0], '+12405550101')
        self.assertIn('250 included', args[1])
        self.assertIn('$0.29', args[1])
        self.assertIn('/shop-one/admin/ai-usage', args[1])
        self.assertEqual(kwargs['shop_id'], self.shop.id)
        self.assertEqual(kwargs['purpose'], 'ai-usage-threshold')

if __name__ == '__main__':
    unittest.main()
