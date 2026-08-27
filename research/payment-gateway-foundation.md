# Payment Gateway Foundation References

The gateway integration will keep order creation and signature verification on the server, create a local immutable payment attempt before opening a hosted or provider checkout, and use an idempotent webhook/event ledger as the source of truth for entitlement changes.

Razorpay documents webhook delivery for orders and payments, including payment-state snapshots: https://razorpay.com/docs/webhooks/ and https://razorpay.com/docs/webhooks/orders/

Stripe documents using webhook events for asynchronous payment confirmation and checkout fulfillment: https://docs.stripe.com/webhooks and https://docs.stripe.com/checkout/fulfillment

Paytm documents callback/webhook handling and checksum verification for payment-gateway requests: https://www.paytmpayments.com/docs/callback-and-webhook and https://www.paytmpayments.com/docs/checksum

No provider credentials have been configured. The implementation therefore returns a clear configuration-pending response and never fabricates a checkout, verifies a webhook with a dummy secret, or marks a payment as paid without a verified provider event.

## Verified design constraints

Stripe requires signature verification and includes a signed timestamp to mitigate replay. It recommends returning a 2xx response quickly and treating asynchronous webhook events, rather than browser redirects, as payment confirmation. Razorpay distinguishes a checkout callback from server-to-server webhooks and requires webhooks for durable payment status. The shared AiMarket integration therefore stores the raw payload hash, deduplicates provider event IDs, keeps a verified event ledger, and changes internal payment status only after signature validation.
