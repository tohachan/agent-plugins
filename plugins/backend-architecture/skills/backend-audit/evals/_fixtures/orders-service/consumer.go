package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"

	"github.com/segmentio/kafka-go"
)

func RunShipmentConsumer(db *sql.DB) {
	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{"kafka:9092"},
		GroupID: "shipments",
		Topic:   "order-events",
	})
	for {
		m, err := r.ReadMessage(context.Background()) // commits offset automatically
		if err != nil {
			log.Println(err)
			continue
		}
		go func(m kafka.Message) {
			var ev struct {
				OrderID int64  `json:"order_id"`
				Type    string `json:"type"`
			}
			json.Unmarshal(m.Value, &ev)
			if _, err := db.Exec("INSERT INTO shipments(order_id) VALUES($1)", ev.OrderID); err != nil {
				log.Println("shipment insert failed:", err)
			}
		}(m)
	}
}
