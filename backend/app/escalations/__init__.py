"""Human escalation & notification service (Phase 3).

Real-time intervention path for the autonomous MRV platform: when agents or
system components cannot proceed autonomously, an :class:`EscalationEvent` is
raised and dispatched to human operators over configurable channels
(WhatsApp, SMS, email, in-app WebSocket push).
"""
