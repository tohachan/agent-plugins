package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type PaymentClient struct {
	base string
	http *http.Client
}

func NewPaymentClient(base string) *PaymentClient {
	return &PaymentClient{base: base, http: &http.Client{}}
}

// Charge retries up to 5 times so transient provider errors don't fail orders.
func (c *PaymentClient) Charge(card string, amountCents int) error {
	body, _ := json.Marshal(map[string]any{"card": card, "amount": amountCents})
	var lastErr error
	for i := 0; i < 5; i++ {
		resp, err := c.http.Post(c.base+"/v1/charges", "application/json", bytes.NewReader(body))
		if err == nil && resp.StatusCode < 300 {
			return nil
		}
		lastErr = fmt.Errorf("charge failed: %v", err)
		time.Sleep(200 * time.Millisecond)
	}
	return lastErr
}
