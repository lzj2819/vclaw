"""L1 User Interaction Layer Tests.

Tests for all L1 components:
- ProtocolAdapters: Telegram, WebSocket, HttpWebhook
- DataValidator: Input validation with security checks
- EventNormalizer: Data format conversion
- ErrorHandler: Retry mechanism with exponential backoff
- UserInteraction: Integration of all components
"""
