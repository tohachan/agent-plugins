package billing

import (
	"context"
	"time"

	"github.com/google/uuid"
)

type Provider interface {
	Charge(ctx context.Context, idempotencyKey string, invoiceID string, amountCents int64) (string, error)
}

// ChargeInvoice charges an invoice and retries transient provider failures.
func ChargeInvoice(ctx context.Context, p Provider, invoiceID string, amountCents int64) (string, error) {
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
		chargeID, err := p.Charge(ctx, uuid.NewString(), invoiceID, amountCents)
		cancel()
		if err == nil {
			return chargeID, nil
		}
		lastErr = err
		time.Sleep(time.Duration(attempt+1) * 200 * time.Millisecond)
	}
	return "", lastErr
}
