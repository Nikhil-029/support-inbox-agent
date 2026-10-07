# API & Integrations

## Where do I find my API key?
Settings > Developer > API Keys. You can generate multiple keys and name
each one (useful for separating staging vs production usage). Keys are
shown in full only once at creation -- store it somewhere safe.

## What are the API rate limits?
Free and Pro plans are limited to 100 requests/minute. Business and
Enterprise plans are limited to 1,000 requests/minute. Exceeding the limit
returns an HTTP 429 with a `Retry-After` header indicating how many seconds
to wait before retrying.

## Do you have a Zapier integration?
Yes -- search "Northbeam Analytics" in the Zapier app directory. It
supports triggers for new events and actions for creating/updating
records. A native Make.com integration is on our roadmap but not yet
available.

## Why is my webhook not firing?
The most common cause is an endpoint that doesn't return a 2xx status code
within 10 seconds -- we retry failed webhooks 3 times with exponential
backoff, then mark the delivery as failed. Check Settings > Developer >
Webhook Logs to see delivery attempts and response codes for each one.
