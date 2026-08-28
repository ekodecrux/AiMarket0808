# Mobile Identity Foundation

## Google identity

Google’s server-side ID-token verification guidance requires validation of the token signature against Google’s rotating public keys, the expected application client-ID audience, an issuer of `accounts.google.com` or `https://accounts.google.com`, and an unexpired `exp` claim. The mobile client must deliver an ID token to the AiMarket backend; it must never be treated as a session token without verification. Source: <https://developers.google.com/identity/gsi/web/guides/verify-google-id-token>.

## SMS OTP

Twilio Verify uses a persistent Verify Service, then starts an SMS verification by sending an E.164 recipient phone number and `sms` channel to the provider. The application must subsequently use Twilio’s Verification Check API to decide whether to issue an AiMarket session. Twilio states that recipient consent must be obtained and documented before an SMS OTP is sent. Server calls use HTTPS and authenticated credentials; those credentials must remain server-side. Sources: <https://www.twilio.com/docs/verify/api> and <https://www.twilio.com/docs/verify/sms>.

## Product decision

Google and SMS verification should yield the same AiMarket tenant-scoped JWT session as password login. The phone number and Google account identity should be normalized and uniquely indexed; successful verification should update a persistent session rather than requiring users to enter credentials on every app opening.
